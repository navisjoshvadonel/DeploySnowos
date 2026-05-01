from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
import sqlite3
import json
import os
import time
import asyncio
import uuid
import subprocess
import requests
from typing import List, Dict, Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI(title="SnowOS ANIL Backend")
from ai_core.nyx_kernel.identity.user import User, Role
from ai_core.nyx_kernel.identity.store import UserStore
# Paths
NYX_DIR = os.path.expanduser("~/snowos/nyx")
if not os.path.exists(NYX_DIR):
    # Fallback for different environments
    NYX_DIR = os.path.join(os.getcwd(), "nyx")

# Identity & Auth
from ai_core.nyx_kernel.identity.store import UserStore
from ai_core.nyx_kernel.identity.auth import verify_password, create_access_token, decode_access_token
from ai_core.nyx_kernel.distributed_identity.node_store import NodeStore
from ai_core.nyx_kernel.distributed_identity.trust import TrustManager

user_store = UserStore(os.path.join(NYX_DIR, "nyx_identity.db"))
node_store = NodeStore(os.path.join(NYX_DIR, "nyx_network.db"))
trust_manager = TrustManager(node_store)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # Try standard local JWT first
    payload = decode_access_token(token)
    if payload:
        user_id = payload.get("sub")
        user_data = user_store.get_user_by_id(user_id)
        if user_data:
            return user_data

    # Try distributed token (DITL)
    try:
        # Distributed tokens might be sent as JSON strings in the header
        token_data = json.loads(token)
        node_id = token_data.get("node_origin")
        if node_id:
            if trust_manager.verify_node_token(node_id, token_data):
                return {
                    "user_id": token_data["user_id"],
                    "role": token_data["role"],
                    "username": f"remote:{token_data['user_id'][:8]}",
                    "node_origin": node_id
                }
    except Exception:
        pass
        pass
    
    raise HTTPException(status_code=401, detail="Invalid or expired token")

def check_role(required_roles: List[Role]):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in [r.value for r in required_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATHS = {
    "observability": os.path.join(NYX_DIR, "nyx_observability.db"),
    "deterministic": os.path.join(NYX_DIR, "nyx_deterministic.db"),
    "state": os.path.join(NYX_DIR, "nyx_state.db")
}

def get_db_conn(db_type: str):
    path = DB_PATHS.get(db_type)
    if not path or not os.path.exists(path):
        return None
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- Frontend Serving ---
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/shell")
async def serve_shell():
    return FileResponse(os.path.join(FRONTEND_DIR, "frostshell.html"))

# --- Auth Endpoints ---

@app.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_store.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user["user_id"], "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "role": current_user["role"]
    }

# --- Node Info (DITL) ---

@app.get("/api/node/info")
async def get_node_info():
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    return {
        "node_id": nyx.node_id,
        "public_key": nyx.node_pub_key.decode() if isinstance(nyx.node_pub_key, bytes) else nyx.node_pub_key
    }

# --- API Endpoints ---

@app.get("/api/goals")
async def get_goals(current_user: dict = Depends(get_current_user)):
    conn = get_db_conn("observability")
    if not conn: return []
    query = "SELECT * FROM spans WHERE type = 'goal'"
    params = []
    if current_user["role"] != "admin":
        query += " AND user_id = ?"
        params.append(current_user["user_id"])
    query += " ORDER BY start_time DESC LIMIT 50"
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.get("/api/trace/{trace_id}")
async def get_trace(trace_id: str, current_user: dict = Depends(get_current_user)):
    conn = get_db_conn("observability")
    if not conn: return []
    query = "SELECT * FROM spans WHERE trace_id = ?"
    params = [trace_id]
    if current_user["role"] != "admin":
        query += " AND user_id = ?"
        params.append(current_user["user_id"])
    query += " ORDER BY start_time ASC"
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.get("/api/metrics")
async def get_metrics(current_user: dict = Depends(get_current_user)):
    conn = get_db_conn("observability")
    if not conn: return {}
    query = "SELECT name, value, timestamp FROM metrics"
    params = []
    if current_user["role"] != "admin":
        query += " WHERE user_id = ?"
        params.append(current_user["user_id"])
    query += " ORDER BY timestamp DESC LIMIT 100"
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    metrics = {}
    for row in rows:
        name = row['name']
        if name not in metrics: metrics[name] = []
        metrics[name].append({"value": row['value'], "timestamp": row['timestamp']})
    return metrics

@app.get("/api/states")
async def get_states(current_user: dict = Depends(get_current_user)):
    conn = get_db_conn("state")
    if not conn: return []
    query = "SELECT * FROM states"
    params = []
    if current_user["role"] != "admin":
        query += " WHERE user_id = ?"
        params.append(current_user["user_id"])
    query += " ORDER BY timestamp DESC LIMIT 50"
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.get("/api/state/{state_id}")
async def get_state(state_id: str, current_user: dict = Depends(get_current_user)):
    conn = get_db_conn("state")
    if not conn: raise HTTPException(status_code=404)
    query = "SELECT * FROM states WHERE state_id = ?"
    params = [state_id]
    if current_user["role"] != "admin":
        query += " AND user_id = ?"
        params.append(current_user["user_id"])
    state_row = conn.execute(query, params).fetchone()
    if not state_row: raise HTTPException(status_code=404)
    files_rows = conn.execute("SELECT * FROM state_files WHERE state_id = ?", (state_id,)).fetchall()
    state = dict(state_row)
    state['metadata'] = json.loads(state['metadata'])
    state['files'] = [dict(f) for f in files_rows]
    return state

@app.get("/api/state/diff/{id1}/{id2}")
async def get_state_diff(id1: str, id2: str, current_user: dict = Depends(get_current_user)):
    conn = get_db_conn("state")
    if not conn: return []
    cursor = conn.execute("SELECT diff_json FROM state_diffs WHERE (from_state = ? AND to_state = ?) OR (from_state = ? AND to_state = ?)", (id1, id2, id2, id1))
    row = cursor.fetchone()
    return json.loads(row['diff_json']) if row else []

@app.get("/api/scheduler/status")
async def get_scheduler_status(current_user: dict = Depends(get_current_user)):
    conn = get_db_conn("observability")
    if not conn: return {"active_workers": 0, "pending_tasks": 0, "recent_events": []}
    active = conn.execute("SELECT COUNT(*) FROM scheduling_events WHERE status = 'RUNNING'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM scheduling_events WHERE status = 'PENDING'").fetchone()[0]
    cursor = conn.execute("SELECT * FROM scheduling_events ORDER BY enqueue_time DESC LIMIT 10")
    return {
        "active_workers": active,
        "pending_tasks": pending,
        "recent_events": [dict(row) for row in cursor.fetchall()]
    }

@app.get("/api/security/audit")
async def get_security_audit(current_user: dict = Depends(check_role([Role.ADMIN, Role.DEVELOPER]))):
    conn = get_db_conn("observability")
    if not conn: return []
    cursor = conn.execute("SELECT * FROM capability_events ORDER BY timestamp DESC LIMIT 50")
    return [dict(row) for row in rows] if (rows := cursor.fetchall()) else []

@app.get("/api/insights")
async def get_insights(current_user: dict = Depends(get_current_user)):
    insights_path = os.path.join(NYX_DIR, "insights.json")
    if os.path.exists(insights_path):
        with open(insights_path) as f:
            return json.load(f)
    return []

# --- Node Management (DITL) ---

@app.get("/api/nodes")
async def get_nodes(current_user: dict = Depends(get_current_user)):
    nodes = node_store.list_nodes()
    return nodes

@app.post("/api/nodes/add")
async def add_node(payload: dict, current_user: dict = Depends(check_role([Role.ADMIN, Role.DEVELOPER]))):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    try:
        # Fetch node info from remote
        info_url = url.rstrip("/") + "/api/node/info"
        res = requests.get(info_url, timeout=5)
        if res.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to fetch node info from {url}")
            
        data = res.json()
        node_id = data.get("node_id")
        pub_key = data.get("public_key")
        
        if not node_id or not pub_key:
            raise HTTPException(status_code=400, detail="Invalid node info received from remote")
            
        node_store.add_node(node_id, url, pub_key)
        return {"status": "success", "node_id": node_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/nodes/trust/{node_id}")
async def trust_node(node_id: str, payload: dict, current_user: dict = Depends(check_role([Role.ADMIN]))):
    trust = payload.get("trust", True)
    status = "trusted" if trust else "untrusted"
    node_store.set_trust(node_id, status)
    return {"status": "success", "trust_status": status}

@app.delete("/api/nodes/{node_id}")
async def remove_node(node_id: str, current_user: dict = Depends(check_role([Role.ADMIN]))):
    node_store.remove_node(node_id)
    return {"status": "success"}

# --- Control Endpoints ---

@app.post("/api/control/replay/{plan_id}")
async def control_replay(plan_id: str, current_user: dict = Depends(check_role([Role.ADMIN, Role.DEVELOPER]))):
    # For now, we trigger the CLI command in a background process
    try:
        cmd = ["nyx", "replay", plan_id, "--live"]
        # We start it and don't wait (it might be long)
        subprocess.Popen(cmd)
        return {"status": "started", "plan_id": plan_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control/rollback/{state_id}")
async def control_rollback(state_id: str, current_user: dict = Depends(check_role([Role.ADMIN]))):
    try:
        cmd = ["nyx", "state", "checkout", state_id]
        subprocess.Popen(cmd)
        return {"status": "started", "state_id": state_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Architecture Endpoints (SDSL) ---

@app.get("/api/architecture/graph")
async def get_arch_graph(current_user: dict = Depends(get_current_user)):
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    return nyx.arch_profiler.graph.get_graph_snapshot()

@app.get("/api/architecture/insights")
async def get_arch_insights(current_user: dict = Depends(get_current_user)):
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    return nyx.design_analysis.generate_findings()

@app.get("/api/architecture/proposals")
async def get_arch_proposals(current_user: dict = Depends(get_current_user)):
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    findings = nyx.design_analysis.generate_findings()
    return nyx.refactor_engine.generate_proposals(findings)

@app.post("/api/architecture/simulate")
async def simulate_arch(payload: dict, current_user: dict = Depends(get_current_user)):
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    proposal_id = payload.get("proposal_id")
    findings = nyx.design_analysis.generate_findings()
    proposals = nyx.refactor_engine.generate_proposals(findings)
    prop = next((p for p in proposals if p["id"] == proposal_id), None)
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return nyx.arch_simulator.simulate_proposal(prop)

@app.post("/api/architecture/apply")
async def apply_arch(payload: dict, current_user: dict = Depends(check_role([Role.ADMIN, Role.DEVELOPER]))):
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    proposal_id = payload.get("proposal_id")
    findings = nyx.design_analysis.generate_findings()
    proposals = nyx.refactor_engine.generate_proposals(findings)
    prop = next((p for p in proposals if p["id"] == proposal_id), None)
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    sim = nyx.arch_simulator.simulate_proposal(prop)
    success = nyx.arch_modifier.apply_proposal(prop, sim)
    return {"success": success}

# --- WebSocket for Real-time Updates ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            conn = get_db_conn("observability")
            if conn:
                active_goals = conn.execute("SELECT COUNT(*) FROM spans WHERE type = 'goal' AND status = 'RUNNING'").fetchone()[0]
                queue_size = conn.execute("SELECT COUNT(*) FROM scheduling_events WHERE status = 'PENDING'").fetchone()[0]
                
                update = {
                    "active_goals": active_goals,
                    "queue_size": queue_size,
                    "timestamp": time.time()
                }
                await websocket.send_json(update)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

from ai_core.nyx_kernel.interface.backend.swarm_endpoints import router as swarm_router
app.include_router(swarm_router)

@app.post("/bridge/error")
async def bridge_error(payload: dict):
    from ai_core.nyx_kernel import NyxAI
    # Local-only access check (optional, but good for security)
    # For now, we trust the local bridge_client.py
    nyx = NyxAI(autonomous=False)
    
    command = payload.get("command", "")
    exit_code = payload.get("exit_code", "1")
    error = payload.get("error", "")
    cwd = payload.get("cwd", os.getcwd())
    
    suggestion_data = nyx.analyze_shell_error(command, exit_code, error, cwd)
    return suggestion_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
