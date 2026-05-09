import os
import sys
import socket
import json
import logging
import time
import hmac
import hashlib
import base64
from policy_engine import PolicyEngine
from intent_validator import IntentValidator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PermissionBroker")

RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
SOCKET_PATH = os.path.join(RUNTIME_DIR, "broker.sock")
TOKEN_SECRET = os.environ.get("SNOWOS_BROKER_TOKEN_SECRET", "snowos-broker-local-signing-key")

class PermissionBroker:
    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.intent_validator = IntentValidator()
        self.running = False
        
    def setup_socket(self):
        os.makedirs(RUNTIME_DIR, mode=0o750, exist_ok=True)
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        self.server.listen(5)
        logger.info(f"Broker listening on {SOCKET_PATH}")

    def issue_token(self, source_id, target_resource, action, ttl_seconds=30):
        issued_at = int(time.time())
        payload = {
            "source_id": source_id,
            "target_resource": target_resource,
            "action": action,
            "issued_at": issued_at,
            "expires_at": issued_at + ttl_seconds
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            TOKEN_SECRET.encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        envelope = {"payload": payload, "signature": signature}
        return base64.urlsafe_b64encode(json.dumps(envelope).encode("utf-8")).decode("ascii")

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
        return {
            "status": "GRANTED",
            "token": self.issue_token(source_id, target_resource, action),
            "expires_in": 30
        }

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
