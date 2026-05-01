import os
import psutil
import logging

class ResourceManager:
    """Arbitrates resource allocation between SnowOS modules."""
    
    def __init__(self, profiler=None):
        self.profiler = profiler
        self.logger = logging.getLogger("SnowOS.ResourceManager")
        self.priority_map = {
            "critical": -15, # System stability / Input
            "high": -10,     # Active UI / Shell
            "normal": 0,     # General AI Reasoning
            "low": 10,       # Background Learning
            "idle": 19       # Housekeeping / Cleanup
        }

    def get_policy(self, system_health):
        """Determine resource policy based on current health."""
        cpu = system_health.get("cpu", 0)
        ram = system_health.get("ram", 0)
        
        if cpu > 90 or ram > 95:
            return "critical_only"
        elif cpu > 70:
            return "throttled"
        else:
            return "full_autonomy"

    def apply_priority(self, module_name, level):
        """Attempt to set the process priority for a module."""
        priority = self.priority_map.get(level, 0)
        try:
            p = psutil.Process(os.getpid())
            # Note: setting negative priorities usually requires root.
            # We'll stick to positive (lower priority) adjustments for safety.
            if priority >= 0:
                p.nice(priority)
                self.logger.info(f"Resource: Set '{module_name}' to {level} priority (nice: {priority})")
        except Exception as e:
            self.logger.debug(f"Priority adjustment failed (likely permissions): {e}")

    def get_throttle_limit(self, mode):
        """Returns the delay (in seconds) to inject between non-critical tasks."""
        if mode == "throttled":
            return 0.5
        elif mode == "critical_only":
            return 2.0
        return 0.0
