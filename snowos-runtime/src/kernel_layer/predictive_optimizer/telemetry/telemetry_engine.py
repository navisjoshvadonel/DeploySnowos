import logging
import time

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("TelemetryEngine")

class TelemetryEngine:
    def __init__(self):
        self.history = []

    def gather_snapshot(self):
        """Return a bounded snapshot of the current machine load."""
        if psutil is None:
            logger.warning("psutil is unavailable; predictive optimizer is idle")
            return {"timestamp": time.time(), "cpu_total": 0.0, "ram_total": 0.0, "processes": []}

        processes = []
        current_pid = psutil.Process().pid
        for process in psutil.process_iter(["pid", "name", "cpu_percent", "nice"]):
            try:
                info = process.info
                if info["pid"] in (0, 1, current_pid):
                    continue
                cpu = float(info["cpu_percent"] or 0.0)
                if cpu <= 0:
                    continue
                processes.append({
                    "name": info["name"] or str(info["pid"]),
                    "pid": info["pid"],
                    "cpu": cpu,
                    "state": "background" if (info["nice"] or 0) > 0 else "foreground",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        snapshot = {
            "timestamp": time.time(),
            "cpu_total": psutil.cpu_percent(interval=0.1),
            "ram_total": psutil.virtual_memory().percent,
            "processes": processes,
        }
        
        self.history.append(snapshot)
        if len(self.history) > 60:
            self.history.pop(0)
            
        logger.debug(f"Gathered snapshot: CPU {snapshot['cpu_total']}%")
        return snapshot
