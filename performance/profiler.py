import time
import logging
from collections import deque

class NyxProfiler:
    """Tracks per-module latency and resource consumption."""
    
    def __init__(self):
        self.logger = logging.getLogger("SnowOS.Profiler")
        # Store last 100 execution times per module
        self.history = {}
        # Thresholds for warnings (in seconds)
        self.thresholds = {
            "nyx.reasoning": 0.200,
            "ui.rendering": 0.016, # 60fps
            "system.io": 0.500
        }

    def start(self, module):
        """Start a profiling span."""
        return {"module": module, "start": time.time()}

    def stop(self, span):
        """End a span and record results."""
        duration = time.time() - span["start"]
        module = span["module"]
        
        if module not in self.history:
            self.history[module] = deque(maxlen=100)
        
        self.history[module].append(duration)
        
        limit = self.thresholds.get(module, 1.0)
        if duration > limit:
            self.logger.warning(f"Performance Alert: '{module}' took {int(duration*1000)}ms (Target: {int(limit*1000)}ms)")
            
        return duration

    def get_stats(self):
        """Return average latencies."""
        stats = {}
        for module, times in self.history.items():
            if times:
                stats[module] = {
                    "avg": sum(times) / len(times),
                    "max": max(times),
                    "p95": sorted(list(times))[int(len(times)*0.95)] if len(times) >= 20 else max(times)
                }
        return stats
