import logging
from secure_surface_manager import SecureSurfaceManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WaylandBridge")

class SnowWaylandBridge:
    def __init__(self):
        self.surface_manager = SecureSurfaceManager()
        self.active_apps = []

    def spawn_app_window(self, app_id):
        logger.info(f"Attempting to spawn window for {app_id}...")
        if self.surface_manager.request_draw(app_id):
            self.active_apps.append(app_id)
            logger.info(f"Window spawned successfully for {app_id}")
            return True
        else:
            logger.error(f"Failed to spawn window: {app_id} lacks drawing permissions.")
            return False

    def route_keystroke(self, app_id, key):
        logger.info(f"Routing keystroke '{key}' to active window ({app_id})...")
        if self.surface_manager.request_input(app_id, "hardware.keyboard"):
            logger.info(f"Keystroke '{key}' delivered to {app_id}")
            return True
        else:
            logger.critical(f"KEYLOGGER PREVENTION: Intercepted unauthorized keystroke read by {app_id}")
            return False

if __name__ == "__main__":
    # Simulated run
    bridge = SnowWaylandBridge()
    bridge.spawn_app_window("app.mock_app")
    bridge.route_keystroke("app.mock_app", "ENTER")
