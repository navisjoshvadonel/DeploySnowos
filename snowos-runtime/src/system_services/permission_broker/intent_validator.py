import logging
import socket
import json
import os

logger = logging.getLogger("IntentValidator")
RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
SENTINEL_SOCKET = os.path.join(RUNTIME_DIR, "sentinel.sock")
ALLOW_DEGRADED = os.environ.get("SNOWOS_ALLOW_DEGRADED_SENTINEL", "0") == "1"

class IntentValidator:
    def __init__(self):
        pass
        
    def validate_intent(self, payload):
        """
        Connects to the AI Sentinel for behavioral analysis.
        """
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(SENTINEL_SOCKET)
                client.sendall(json.dumps(payload).encode('utf-8'))
                response_data = client.recv(4096)
                response = json.loads(response_data.decode('utf-8'))
                
                if response.get("status") == "BLOCK":
                    logger.warning(f"AI Sentinel blocked request. Score: {response.get('score')}")
                    return False
                return True
        except FileNotFoundError:
            logger.warning("AI Sentinel not running.")
            return ALLOW_DEGRADED
        except Exception as e:
            logger.error(f"Error communicating with Sentinel: {e}")
            return ALLOW_DEGRADED
