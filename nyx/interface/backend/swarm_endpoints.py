from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
import os

router = APIRouter(prefix="/swarm", tags=["swarm"])

@router.post("/learn")
async def swarm_learn(payload: dict):
    """Ingest insights from a swarm peer."""
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    insights = payload.get("insights", [])
    if insights:
        nyx.swarm_learning.ingest_remote_insights(insights)
    return {"status": "ingested", "count": len(insights)}

@router.post("/delegate")
async def swarm_delegate(payload: dict):
    """Execute a task delegated by a swarm peer."""
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    
    goal = payload.get("goal")
    cwd = payload.get("cwd", os.getcwd())
    goal_id = payload.get("goal_id")
    
    if not goal:
        raise HTTPException(status_code=400, detail="Goal required")
        
    tid = nyx.scheduler.schedule(goal=goal, cwd=cwd, goal_id=goal_id)
    return {"status": "scheduled", "task_id": tid}

@router.get("/heartbeat")
async def swarm_heartbeat():
    """Health check for swarm peering."""
    from ai_core.nyx_kernel import NyxAI
    nyx = NyxAI(autonomous=False)
    return {
        "node_id": nyx.node_id,
        "load": os.getloadavg()[0],
        "status": "active"
    }
