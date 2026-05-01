import os
import socket
import json
import logging
from threat_model import ThreatModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AISentinel")

SOCKET_PATH = "/tmp/snowos_sentinel.sock"

class SentinelDaemon:
    def __init__(self):
        self.threat_model = ThreatModel()
        self.running = False
        
    def setup_socket(self):
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o777)
        self.server.listen(5)
        logger.info(f"AI Sentinel active on {SOCKET_PATH}")

    def handle_request(self, payload_str):
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            return {"status": "ERROR", "reason": "Invalid JSON"}
            
        source_id = payload.get("source_id")
        logger.info(f"Analyzing behavior for: {source_id}")
        
        risk_score = self.threat_model.evaluate(payload)
        
        if risk_score >= 0.8:
            logger.critical(f"THREAT DETECTED from {source_id} (Score: {risk_score:.2f}) -> BLOCKING ACTION")
            return {"status": "BLOCK", "score": risk_score}
            
        logger.info(f"Behavior normal for {source_id} (Score: {risk_score:.2f})")
        return {"status": "ALLOW", "score": risk_score}

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
            logger.info("Sentinel shutting down...")
        finally:
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

if __name__ == "__main__":
    sentinel = SentinelDaemon()
    sentinel.run()
