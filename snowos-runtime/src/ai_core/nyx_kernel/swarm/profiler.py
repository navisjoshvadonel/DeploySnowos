import os
import psutil
import time
import json
import threading
import socket
from typing import Dict, Any

class NodeProfiler:
    """
    Stage 41 — Node Profiling System.
    Gathers and maintains real-time resource metrics for the local node.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.hostname = socket.gethostname()
        self.metrics = {
            "cpu_capacity": psutil.cpu_count(),
            "mem_total": psutil.virtual_memory().total,
            "current_load": 0.0,
            "mem_used": 0.0,
            "disk_used": 0.0,
            "success_rate": 1.0,
            "avg_latency": 0.0,
            "last_update": 0
        }
        self._history = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._profiling_loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def get_profile(self) -> Dict[str, Any]:
        """Returns the current node profile."""
        with self._lock:
            return {
                "node_id": self.node_id,
                "hostname": self.hostname,
                **self.metrics
            }

    def _profiling_loop(self):
        while not self._stop_event.is_set():
            try:
                self._update_metrics()
            except Exception:
                pass
            time.sleep(10)

    def _update_metrics(self):
        with self._lock:
            self.metrics["current_load"] = psutil.cpu_percent(interval=1)
            self.metrics["mem_used"] = psutil.virtual_memory().percent
            self.metrics["disk_used"] = psutil.disk_usage('/').percent
            self.metrics["last_update"] = time.time()
            
            # Historical tracking
            self._history.append({
                "ts": self.metrics["last_update"],
                "cpu": self.metrics["current_load"],
                "mem": self.metrics["mem_used"]
            })
            # Keep only last hour (60 points if every 1 min, here every 10s -> 360 points)
            if len(self._history) > 360:
                self._history.pop(0)

    def record_execution(self, success: bool, duration: float):
        """Update historical performance metrics."""
        with self._lock:
            # Simple moving average for success rate and latency
            alpha = 0.1
            self.metrics["success_rate"] = (1 - alpha) * self.metrics["success_rate"] + alpha * (1.0 if success else 0.0)
            self.metrics["avg_latency"] = (1 - alpha) * self.metrics["avg_latency"] + alpha * duration
