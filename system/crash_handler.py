import traceback
import logging
import time

class CrashHandler:
    """Captures failures and manages the safe restoration of system state."""
    
    def __init__(self, sys_logger):
        self.logger = sys_logger
        self.internal_logger = logging.getLogger("SnowOS.CrashHandler")

    def capture(self, module_name, exception):
        """Log a crash and broadcast recovery intent."""
        stack_trace = traceback.format_exc()
        self.internal_logger.error(f"CRASH in {module_name}: {exception}")
        
        # Record structured event
        self.logger.event(module_name, "CRASH", {
            "error": str(exception),
            "trace": stack_trace
        })
        
        # Broadcast for UI/Runtime to handle
        from runtime.event_bus import bus
        bus.publish("system_incident", {
            "type": "crash",
            "module": module_name,
            "error": str(exception),
            "can_auto_recover": True
        })

    def recover_module(self, module_name):
        """Perform a safe reset of a specific subsystem (stub)."""
        self.internal_logger.info(f"CrashHandler: Initiating safe-reset for {module_name}")
        # In a real OS, this would involve re-importing modules or restarting threads
        from runtime.event_bus import bus
        bus.publish("module_restart", {"module": module_name})
        return True
