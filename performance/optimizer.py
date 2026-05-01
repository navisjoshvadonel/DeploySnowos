import logging

class PerformanceOptimizer:
    """The intelligence layer that switches OS performance modes."""
    
    def __init__(self, profiler, resource_manager, scheduler):
        self.profiler = profiler
        self.rm = resource_manager
        self.scheduler = scheduler
        self.logger = logging.getLogger("SnowOS.Optimizer")
        self.current_mode = "balanced"

    def analyze_and_apply(self, health_data):
        """Analyze health and potentially shift modes."""
        cpu = health_data.get("cpu", 0)
        
        target_mode = "balanced"
        if cpu > 85:
            target_mode = "performance"
        elif cpu < 20:
            target_mode = "intelligent"
            
        if target_mode != self.current_mode:
            self._shift_mode(target_mode)

    def _shift_mode(self, mode):
        """Apply performance profiles system-wide."""
        self.current_mode = mode
        self.logger.info(f"Performance: Shifting to {mode.upper()} mode")
        
        # Publish shift to event bus
        from runtime.event_bus import bus
        bus.publish("perf_mode_shift", {
            "mode": mode,
            "throttling": self.rm.get_throttle_limit(mode)
        })
        
        # Adjust background priorities
        if mode == "performance":
            self.rm.apply_priority("learning", "idle")
            self.rm.apply_priority("ui", "high")
        elif mode == "intelligent":
            self.rm.apply_priority("learning", "normal")
            self.rm.apply_priority("ui", "normal")
