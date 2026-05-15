import psutil
from collections import defaultdict
from .storage import Storage
import json

class MetricsCollector:
    def __init__(self, storage: Storage):
        self.storage = storage

    def system_metrics(self):
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {}
        }

    def record_command(self, latency, status, command=None):
        metadata = {"command": command} if command else {}
        self.storage.save_metric("command_latency", latency, status, metadata=metadata)

    def summary(self):
        metrics = self.storage.get_all_metrics(name="command_latency")
        
        if not metrics:
            return {
                "avg_latency": 0,
                "p95_latency": 0,
                "total_commands": 0,
                "success_rate": 0,
                "status_breakdown": {},
                "top_slow_commands": [],
                "system": self.system_metrics()
            }
            
        latencies = [m["value"] for m in metrics]
        total_commands = len(latencies)
        avg_latency = sum(latencies) / total_commands
        
        sorted_latencies = sorted(latencies)
        p95_idx = int(total_commands * 0.95)
        p95_latency = sorted_latencies[min(p95_idx, total_commands - 1)]
        
        status_breakdown = defaultdict(int)
        for m in metrics:
            status_breakdown[m["status"]] += 1
            
        success_count = status_breakdown.get("SUCCESS", 0)
        success_rate = (success_count / total_commands) * 100 if total_commands > 0 else 0
        
        # Top slow commands
        # Each metric has metadata with the command
        command_stats = []
        for m in metrics:
            meta = json.loads(m["metadata"]) if isinstance(m["metadata"], str) else m["metadata"]
            cmd = meta.get("command", "unknown")
            command_stats.append({"command": cmd, "latency": m["value"]})
            
        top_slow = sorted(command_stats, key=lambda x: x["latency"], reverse=True)[:5]

        return {
            "avg_latency": avg_latency,
            "p95_latency": p95_latency,
            "total_commands": total_commands,
            "success_rate": success_rate,
            "status_breakdown": dict(status_breakdown),
            "top_slow_commands": top_slow,
            "system": self.system_metrics()
        }

    def check_thresholds(self, summary):
        actions = []
        if summary["p95_latency"] > 2.0:
            actions.append({
                "type": "OPTIMIZATION_REQUIRED",
                "message": f"High P95 latency detected: {summary['p95_latency']:.2f}s"
            })
        
        if summary["success_rate"] < 90.0:
            actions.append({
                "type": "SYSTEM_ALERT",
                "message": f"Low success rate: {summary['success_rate']:.1f}%"
            })
            
        return actions
