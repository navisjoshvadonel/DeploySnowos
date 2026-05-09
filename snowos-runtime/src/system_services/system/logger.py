import json
import os
import time
import logging

class SnowLogger:
    """Unified JSON logging for all SnowOS subsystems."""
    
    def __init__(self):
        self.log_dir = os.path.expanduser("~/.snowos/system")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(self.log_dir, "snowos.log")
        
        # Configure standard logging for internal use
        self.logger = logging.getLogger("SnowOS.System")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_path)
            self.logger.addHandler(handler)

    def event(self, module, name, data=None):
        """Log a structured system event."""
        entry = {
            "timestamp": time.time(),
            "module": module,
            "event": name,
            "data": data or {}
        }
        
        # Write to log file as JSON-line
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

        # Publish to EventBus for dashboard/real-time subscribers
        try:
            from runtime.event_bus import bus
            bus.publish("system_event", entry)
        except ImportError:
            pass

    def get_recent(self, limit=50):
        """Retrieve recent log entries."""
        try:
            with open(self.log_path, "r") as f:
                lines = f.readlines()
                return [json.loads(l) for l in lines[-limit:]]
        except Exception:
            return []
