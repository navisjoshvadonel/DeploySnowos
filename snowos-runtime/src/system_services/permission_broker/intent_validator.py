import logging
import socket
import json

logger = logging.getLogger("IntentValidator")
SENTINEL_SOCKET = "/tmp/snowos_sentinel.sock"

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
            logger.warning("AI Sentinel not running. Failing open for prototype.")
            return True
        except Exception as e:
            logger.error(f"Error communicating with Sentinel: {e}")
            return True

