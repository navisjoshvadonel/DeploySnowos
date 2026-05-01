import os
import sys
import socket
import json
import logging
from policy_engine import PolicyEngine
from intent_validator import IntentValidator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PermissionBroker")

SOCKET_PATH = "/tmp/snowos_broker.sock"

class PermissionBroker:
    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.intent_validator = IntentValidator()
        self.running = False
        
    def setup_socket(self):
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o777) # For prototype
        self.server.listen(5)
        logger.info(f"Broker listening on {SOCKET_PATH}")

    def handle_request(self, payload_str):
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            return {"status": "ERROR", "reason": "Invalid JSON"}
            
        source_id = payload.get("source_id")
        target_resource = payload.get("target_resource")
        action = payload.get("action")
        
        if not all([source_id, target_resource, action]):
            return {"status": "ERROR", "reason": "Missing required fields"}
            
        logger.info(f"Request: {source_id} -> {action} on {target_resource}")
        
        # 1. Check Capabilities
        if not self.policy_engine.evaluate(source_id, target_resource, action):
            logger.warning(f"DENIED: {source_id} lacks capability for {action} on {target_resource}")
            return {"status": "DENIED", "reason": "Capability not granted"}
            
        # 2. Check Intent (AI Sentinel Hook)
        if not self.intent_validator.validate_intent(payload):
            logger.warning(f"DENIED: Intent validation failed for {source_id}")
            return {"status": "DENIED", "reason": "Suspicious intent detected"}
            
        logger.info(f"GRANTED: {source_id} -> {action} on {target_resource}")
        return {"status": "GRANTED", "token": "prototype_temporal_token_123"}

    def run(self):
        self.setup_socket()
        self.running = True
        
        try:
            while self.running:
                conn, addr = self.server.accept()
                with conn:
                    data = conn.recv(4096)
                    if not data:
                        continue
                    
                    response = self.handle_request(data.decode('utf-8'))
                    conn.sendall(json.dumps(response).encode('utf-8'))
        except KeyboardInterrupt:
            logger.info("Broker shutting down...")
        finally:
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

if __name__ == "__main__":
    broker = PermissionBroker()
    broker.run()
