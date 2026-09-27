import traceback
import logging
import time
from typing import Dict, Any, Optional, Callable

from kernel_layer.performance.nj_engine import NJFaultDomain, ComponentHealthState

class CrashHandler:
    """
    NJ-Powered Crash Resilience & Fault Isolation Subsystem.
    Isolates crashed AI models or user applications within protected fault domains,
    restoring state via snapshots without taking down the host OS or requiring a reboot.
    """
    
    def __init__(self, sys_logger=None):
        self.logger = sys_logger
        self.internal_logger = logging.getLogger("SnowOS.CrashHandler")
        self.domains: Dict[str, NJFaultDomain] = {}

    def get_or_create_domain(
        self,
        module_name: str,
        failure_threshold: int = 3,
        quarantine_duration_sec: float = 15.0,
        fallback_fn: Optional[Callable[[Exception, Any], Any]] = None,
    ) -> NJFaultDomain:
        """Retrieve or register an isolated fault domain for an AI model or service."""
        if module_name not in self.domains:
            self.domains[module_name] = NJFaultDomain(
                name=module_name,
                failure_threshold=failure_threshold,
                quarantine_duration_sec=quarantine_duration_sec,
                fallback_fn=fallback_fn,
            )
        return self.domains[module_name]

    def run_safe(
        self,
        module_name: str,
        target_fn: Callable,
        *args,
        state_snapshot: Optional[Dict[str, Any]] = None,
        rollback_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
        fallback_fn: Optional[Callable[[Exception, Any], Any]] = None,
        **kwargs
    ):
        """
        Execute an unverified task inside the module's NJ Fault Domain cage.
        Guarantees system continuity without kernel crash or reboot.
        """
        domain = self.get_or_create_domain(module_name, fallback_fn=fallback_fn)
        success, result = domain.execute(
            target_fn,
            *args,
            state_snapshot=state_snapshot,
            rollback_fn=rollback_fn,
            **kwargs
        )
        return success, result

    def capture(self, module_name: str, exception: Exception):
        """Log a crash and record it within the module's fault domain."""
        stack_trace = traceback.format_exc()
        self.internal_logger.error(f"CRASH in {module_name}: {exception}")
        
        domain = self.get_or_create_domain(module_name)
        with domain._lock:
            domain._record_crash_locked(exception, stack_trace, time.monotonic())

        # Record structured event if logger exists
        if self.logger and hasattr(self.logger, "event"):
            self.logger.event(module_name, "CRASH", {
                "error": str(exception),
                "trace": stack_trace,
                "state": domain.state.name,
            })
        
        # Broadcast for UI/Runtime to handle gracefully
        try:
            from runtime.event_bus import bus
            bus.publish("system_incident", {
                "type": "crash",
                "module": module_name,
                "error": str(exception),
                "quarantined": (domain.state == ComponentHealthState.QUARANTINED),
                "can_auto_recover": True
            })
        except ImportError:
            pass

    def recover_module(self, module_name: str):
        """Perform a safe reset of a specific subsystem domain without rebooting the OS."""
        self.internal_logger.info(f"CrashHandler: Initiating NJ safe-reset for {module_name}")
        if module_name in self.domains:
            self.domains[module_name].reset()
        try:
            from runtime.event_bus import bus
            bus.publish("module_restart", {"module": module_name, "status": "restored"})
        except ImportError:
            pass
        return True

    def get_health_ledger(self) -> Dict[str, Any]:
        """Audit all fault domain states across the OS."""
        return {name: domain.get_status() for name, domain in self.domains.items()}
