import logging
import json
import os
import socket

logger = logging.getLogger("CapabilityIssuer")

class CapabilityIssuer:
    def __init__(self):
        runtime_dir = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
        self.socket_path = os.path.join(runtime_dir, "broker.sock")

    def request_token(self, manifest):
        """
        Request a broker-signed token for the module's first declared capability.
        """
        permissions = manifest.get("permissions", {})
        if not isinstance(permissions, dict) or not permissions:
            logger.error("Module %s requested no valid capabilities", manifest.get("name"))
            return None

        target_resource, actions = next(iter(permissions.items()))
        if not isinstance(actions, list) or not actions or not isinstance(actions[0], str):
            logger.error("Module %s has an invalid capability declaration", manifest.get("name"))
            return None

        payload = {
            "source_id": manifest["name"],
            "target_resource": target_resource,
            "action": actions[0],
        }
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(3)
                client.connect(self.socket_path)
                client.sendall(json.dumps(payload).encode("utf-8"))
                response = json.loads(client.recv(4096).decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Capability broker unavailable for %s: %s", manifest["name"], exc)
            return None

        if response.get("status") != "GRANTED" or not response.get("token"):
            logger.warning("Capability request denied for %s: %s", manifest["name"], response.get("reason", "unknown reason"))
            return None
        return response["token"]
