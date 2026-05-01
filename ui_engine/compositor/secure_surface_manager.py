import logging
import socket
import json

logger = logging.getLogger("SurfaceManager")
BROKER_SOCKET = "/tmp/snowos_broker.sock"

class SecureSurfaceManager:
    def __init__(self):
        pass

    def check_permission(self, app_id, resource, action):
        """
        Asks the Permission Broker if the app is allowed to interact with the UI resource.
        """
        payload = {
            "source_id": app_id,
            "target_resource": resource,
            "action": action,
            "context": f"Compositor mediating {action} on {resource}"
        }
        
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(BROKER_SOCKET)
                client.sendall(json.dumps(payload).encode('utf-8'))
                response_data = client.recv(4096)
                response = json.loads(response_data.decode('utf-8'))
                
                if response.get("status") == "GRANTED":
                    return True
                else:
                    logger.warning(f"Compositor blocked {app_id} from {action} on {resource}: {response.get('reason')}")
                    return False
        except Exception as e:
            logger.error(f"Failed to communicate with Permission Broker: {e}")
            return False # Fail closed in the UI for security

    def request_draw(self, app_id):
        if self.check_permission(app_id, "display.surface", "draw"):
            logger.info(f"Granted drawing surface to {app_id}")
            return True
        return False
        
    def request_input(self, app_id, input_type="hardware.keyboard"):
        if self.check_permission(app_id, input_type, "read"):
            logger.info(f"Routing {input_type} input to {app_id}")
            return True
        return False
