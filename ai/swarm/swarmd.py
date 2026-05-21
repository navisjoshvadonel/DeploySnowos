import os
import sys
import json
import ssl
import math
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import local Nyx/SnowOS dependencies
_AI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _AI_DIR)

from distributed_identity.trust import TrustManager
from distributed_identity.node_store import NodeStore
from performance.intent_governor import IntentGovernor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SwarmD] %(message)s")
logger = logging.getLogger("SwarmD")

# Globals for the daemon
governor = IntentGovernor()
# Fake initial creation of NodeStore mapping
with open("/tmp/snowos_nodes.json", "w") as f:
    json.dump({"nodes": {}}, f)
node_store = NodeStore("/tmp/snowos_nodes.json")
trust_engine = TrustManager(node_store)

local_federated_memory = []

def cosine_similarity(v1: list, v2: list) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a*b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a*a for a in v1))
    norm2 = math.sqrt(sum(b*b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

class SwarmHandler(BaseHTTPRequestHandler):
    def _respond(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode("utf-8"))
        except json.JSONDecodeError:
            self._respond(400, {"status": "error", "reason": "Invalid JSON"})
            return

        if self.path == "/memory/sync":
            self._handle_memory_sync(payload)
        elif self.path == "/memory/query":
            self._handle_memory_query(payload)
        elif self.path == "/swarm/execute":
            self._handle_swarm_execute(payload)
        else:
            self._respond(404, {"status": "error", "reason": "Not Found"})

    def _handle_memory_sync(self, payload):
        node_id = payload.get("node_id", "unknown")
        patterns = payload.get("patterns", [])
        logger.info(f"Received memory sync from {node_id}: {len(patterns)} patterns.")
        local_federated_memory.extend(patterns)
        self._respond(200, {"status": "success", "synced": len(patterns)})

    def _handle_memory_query(self, payload):
        query_vector = payload.get("vector", [])
        if not query_vector:
            self._respond(400, {"status": "error", "reason": "No vector provided"})
            return
        
        results = []
        for mem in local_federated_memory:
            if isinstance(mem, dict) and "vector" in mem:
                sim = cosine_similarity(query_vector, mem["vector"])
                results.append({"memory": mem, "score": sim})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        top_k = results[:5]
        logger.info(f"RAG Query processed. Returned {len(top_k)} matches.")
        self._respond(200, {"status": "success", "results": top_k})

    def _handle_swarm_execute(self, payload):
        node_id = payload.get("node_id", "unknown")
        action = payload.get("action", "")
        
        trust_score, is_trusted = trust_engine.evaluate_risk(node_id, action)
        logger.info(f"Execution request from {node_id}. Action: '{action}'. Trust Score: {trust_score}%")
        
        if not is_trusted:
            logger.warning(f"Low trust score ({trust_score}%). Elevating to Intent Governor.")
            gov_check = governor.check_intent(action)
            if not gov_check["safe"]:
                logger.error(f"IntentGovernor BLOCKED action: {gov_check['reason']}")
                self._respond(403, {"status": "blocked", "reason": gov_check["reason"]})
                return
            else:
                logger.info("IntentGovernor approved action despite low trust score.")
                
        logger.info(f"Executing remote action: {action}")
        self._respond(200, {"status": "success", "executed": action})

def run_daemon(port=8443):
    server_address = ('', port)
    httpd = HTTPServer(server_address, SwarmHandler)
    
    cert_file = "/tmp/snowos_cert.pem"
    key_file = "/tmp/snowos_key.pem"
    if os.path.exists(cert_file) and os.path.exists(key_file):
        httpd.socket = ssl.wrap_socket(httpd.socket, keyfile=key_file, certfile=cert_file, server_side=True)
        logger.info(f"SwarmD listening on port {port} (TLS ENABLED)")
    else:
        logger.warning("No TLS certificates found. Falling back to HTTP (Simulated secure socket).")
        logger.info(f"SwarmD listening on port {port} (HTTP)")
        
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down swarmd.")

if __name__ == "__main__":
    run_daemon()
