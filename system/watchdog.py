import time
import logging

class SnowWatchdog:
    """Monitors heartbeats and triggers recovery for hanging modules."""
    
    def __init__(self):
        self.heartbeats = {}
        self.logger = logging.getLogger("SnowOS.Watchdog")
        self.timeout = 10 # Seconds before a module is considered hanging

    def poke(self, module_name):
        """Record a heartbeat from a module."""
        self.heartbeats[module_name] = time.time()

    def audit(self):
        """Check all registered modules for responsiveness."""
        now = time.time()
        crashes = []
        
        for module, last_seen in self.heartbeats.items():
            if now - last_seen > self.timeout:
                self.logger.warning(f"Watchdog: '{module}' has stopped responding (last seen {int(now - last_seen)}s ago)")
                crashes.append(module)
        
        for module in crashes:
            self._trigger_recovery(module)

    def _trigger_recovery(self, module):
        """Broadcast crash event and clear stale heartbeat."""
        from runtime.event_bus import bus
        bus.publish("module_failure", {
            "module": module,
            "timestamp": time.time(),
            "action": "restart_requested"
        })
        # Reset heartbeat to prevent loop during restart
        self.heartbeats[module] = time.time()
        self.logger.info(f"Watchdog: Recovery event published for {module}")
