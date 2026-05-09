import time
import random
import logging

logger = logging.getLogger("TelemetryEngine")

class TelemetryEngine:
    def __init__(self):
        self.history = []

    def gather_snapshot(self):
        """
        Simulate gathering eBPF telemetry or psutil metrics.
        Returns a mock snapshot of active foreground and background load.
        """
        # For prototype, we will simulate a state where a game is launching
        # and background processes are consuming resources.
        snapshot = {
            "timestamp": time.time(),
            "cpu_total": random.randint(60, 95),
            "ram_total": random.uniform(6.0, 8.0),
            "processes": [
                {"name": "app.browser", "pid": 1001, "cpu": 15.0, "state": "background"},
                {"name": "system.updater", "pid": 500, "cpu": 45.0, "state": "background"},
                {"name": "app.game", "pid": 2048, "cpu": 30.0, "state": "foreground"}
            ]
        }
        
        self.history.append(snapshot)
        if len(self.history) > 60:
            self.history.pop(0)
            
        logger.debug(f"Gathered snapshot: CPU {snapshot['cpu_total']}%")
        return snapshot
