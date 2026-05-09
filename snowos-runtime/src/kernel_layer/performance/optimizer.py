import logging
from sysctl_tuner import SysctlTuner


class PerformanceOptimizer:
    """
    The intelligence layer that switches OS performance modes.

    Mode transitions:
      CPU > 85%  → performance  (max throughput, deadline I/O, performance governor)
      CPU 20-85% → balanced     (desktop defaults, mq-deadline I/O, schedutil)
      CPU < 20%  → intelligent  (power-saver, BFQ I/O, background AI learning)

    Each mode shift calls SysctlTuner to apply real kernel parameters.
    """

    _MODES = {
        "performance": "CPU > 85% — maximising throughput",
        "balanced":    "CPU 20-85% — standard desktop profile",
        "intelligent": "CPU < 20% — power-saver / background AI",
    }

    def __init__(self, profiler, resource_manager, scheduler):
        self.profiler = profiler
        self.rm = resource_manager
        self.scheduler = scheduler
        self.logger = logging.getLogger("SnowOS.Optimizer")
        self.current_mode = "balanced"
        # SysctlTuner applies real kernel parameters on every mode shift.
        self._sysctl = SysctlTuner()
        # Apply the startup (balanced) profile immediately.
        self._sysctl.apply_profile("balanced")

    # ── Public API ───────────────────────────────────────────────────────────

    def analyze_and_apply(self, health_data: dict):
        """Analyse system health and shift performance mode if needed."""
        cpu = health_data.get("cpu", 0)

        if cpu > 85:
            target_mode = "performance"
        elif cpu < 20:
            target_mode = "intelligent"
        else:
            target_mode = "balanced"

        if target_mode != self.current_mode:
            self._shift_mode(target_mode)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _shift_mode(self, mode: str):
        """Apply a full performance profile shift — Python priorities + kernel params."""
        self.current_mode = mode
        self.logger.info(
            "Performance: Shifting to %s — %s",
            mode.upper(), self._MODES.get(mode, ""),
        )

        # 1. Apply real kernel-level sysctl parameters.
        sysctl_ok = self._sysctl.apply_profile(mode)
        if not sysctl_ok:
            self.logger.warning(
                "Performance: sysctl profile partially applied — "
                "run SnowOS services as root for full kernel tuning."
            )

        # 2. Publish mode shift to the runtime event bus.
        try:
            from runtime.event_bus import bus
            bus.publish("perf_mode_shift", {
                "mode": mode,
                "throttling": self.rm.get_throttle_limit(mode),
                "sysctl_applied": sysctl_ok,
            })
        except ImportError:
            # Event bus not available in standalone / test context.
            pass

        # 3. Adjust process-level priorities for SnowOS modules.
        if mode == "performance":
            self.rm.apply_priority("learning", "idle")
            self.rm.apply_priority("ui", "high")
            self.rm.apply_priority("ai_core", "normal")
        elif mode == "intelligent":
            # Background AI learning gets normal priority when CPU is idle.
            self.rm.apply_priority("learning", "normal")
            self.rm.apply_priority("ui", "normal")
            self.rm.apply_priority("ai_core", "low")
        else:  # balanced
            self.rm.apply_priority("learning", "low")
            self.rm.apply_priority("ui", "high")
            self.rm.apply_priority("ai_core", "normal")
