"""
SnowOS SysctlTuner — Real Kernel-Level Performance Tuning
==========================================================

This module applies actual Linux kernel parameters (via sysctl) based on the
current SnowOS performance mode. It is called by PerformanceOptimizer whenever
a mode shift occurs.

Three profiles are supported:

  performance  — Maximise throughput. Low swappiness, aggressive CPU scheduler,
                 deadline I/O scheduler, large network buffers. Use when Nyx or
                 heavy workloads are running.

  balanced     — Safe defaults tuned for interactive desktop use. Moderate
                 swappiness, mq-deadline I/O, standard scheduler granularity.

  intelligent  — Power-aware. High swappiness to offload RAM, BFQ I/O scheduler
                 for fair-queued responsiveness, longer scheduler slices to
                 reduce wake-up overhead. Use when system is idle and AI
                 background learning is running.

Design decisions:
  - Writes via `sysctl -w` (requires root at runtime). If root is not available,
    falls back to writing directly to /proc/sys/ where possible.
  - CPU frequency governor is set via cpupower if available, falls back to
    directly writing to /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor.
  - A dry-run mode (SNOWOS_SYSCTL_DRYRUN=1) prints commands without applying.
  - All applied parameters are logged at INFO level for auditability.
"""

import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger("SnowOS.SysctlTuner")

_DRY_RUN: bool = os.environ.get("SNOWOS_SYSCTL_DRYRUN", "0") == "1"

# ─────────────────────────────────────────────────────────────────────────────
# Profile definitions
# ─────────────────────────────────────────────────────────────────────────────

_PROFILES: dict[str, dict] = {
    "performance": {
        # Memory — keep as much data in RAM as possible
        "vm.swappiness": "5",
        "vm.dirty_ratio": "15",
        "vm.dirty_background_ratio": "5",
        "vm.vfs_cache_pressure": "50",
        # CPU scheduler — prioritise latency over fairness
        "kernel.sched_min_granularity_ns": "500000",       # 0.5 ms
        "kernel.sched_wakeup_granularity_ns": "250000",    # 0.25 ms
        "kernel.sched_migration_cost_ns": "5000000",       # 5 ms
        # Network — larger buffers for throughput
        "net.core.rmem_max": "134217728",
        "net.core.wmem_max": "134217728",
        "net.core.netdev_max_backlog": "5000",
        # CPU governor
        "_cpu_governor": "performance",
        # I/O scheduler (applied per block device)
        "_io_scheduler": "deadline",
    },
    "balanced": {
        "vm.swappiness": "10",
        "vm.dirty_ratio": "20",
        "vm.dirty_background_ratio": "10",
        "vm.vfs_cache_pressure": "100",
        "kernel.sched_min_granularity_ns": "1000000",      # 1 ms
        "kernel.sched_wakeup_granularity_ns": "750000",    # 0.75 ms
        "kernel.sched_migration_cost_ns": "3000000",       # 3 ms
        "net.core.rmem_max": "16777216",
        "net.core.wmem_max": "16777216",
        "net.core.netdev_max_backlog": "1000",
        "_cpu_governor": "schedutil",
        "_io_scheduler": "mq-deadline",
    },
    "intelligent": {
        # Power-aware — allow aggressive swap to free RAM for AI inference
        "vm.swappiness": "60",
        "vm.dirty_ratio": "40",
        "vm.dirty_background_ratio": "20",
        "vm.vfs_cache_pressure": "200",
        # Longer scheduler slices reduce context-switch overhead for AI threads
        "kernel.sched_min_granularity_ns": "3000000",      # 3 ms
        "kernel.sched_wakeup_granularity_ns": "2000000",   # 2 ms
        "kernel.sched_migration_cost_ns": "2000000",       # 2 ms
        "net.core.rmem_max": "8388608",
        "net.core.wmem_max": "8388608",
        "net.core.netdev_max_backlog": "500",
        "_cpu_governor": "powersave",
        # BFQ gives fair I/O bandwidth to background learning jobs
        "_io_scheduler": "bfq",
    },
}


class SysctlTuner:
    """
    Applies Linux kernel parameters to match a SnowOS performance profile.

    Usage (called by PerformanceOptimizer):
        tuner = SysctlTuner()
        tuner.apply_profile("performance")
    """

    def __init__(self):
        self._current_profile: Optional[str] = None

    # ── Public API ───────────────────────────────────────────────────────────

    def apply_profile(self, profile: str) -> bool:
        """
        Apply all sysctl parameters for the given profile.

        Returns True if all parameters were applied successfully,
        False if any parameter failed (e.g., not running as root).
        """
        params = _PROFILES.get(profile)
        if not params:
            logger.warning("SysctlTuner: Unknown profile '%s' — no changes applied.", profile)
            return False

        if profile == self._current_profile:
            logger.debug("SysctlTuner: Profile '%s' already active — skipping.", profile)
            return True

        logger.info("SysctlTuner: Shifting to '%s' profile.", profile)
        all_ok = True

        for key, value in params.items():
            if key.startswith("_"):
                # Special directives handled separately below
                continue
            ok = self._sysctl_write(key, value)
            if not ok:
                all_ok = False

        # CPU governor
        governor = params.get("_cpu_governor")
        if governor:
            self._set_cpu_governor(governor)

        # I/O scheduler
        io_sched = params.get("_io_scheduler")
        if io_sched:
            self._set_io_scheduler(io_sched)

        if all_ok:
            self._current_profile = profile
            logger.info("SysctlTuner: Profile '%s' applied successfully.", profile)
        else:
            logger.warning(
                "SysctlTuner: Profile '%s' partially applied — some params may require root.",
                profile,
            )

        return all_ok

    def read_current(self, key: str) -> Optional[str]:
        """Read a sysctl value from the running kernel."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", key],
                capture_output=True, text=True, timeout=3,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _sysctl_write(self, key: str, value: str) -> bool:
        """
        Write a sysctl parameter.
        Tries `sysctl -w` first; falls back to direct /proc/sys/ write.
        """
        if _DRY_RUN:
            logger.info("[DRY RUN] sysctl -w %s=%s", key, value)
            return True

        # Primary: sysctl -w
        try:
            result = subprocess.run(
                ["sysctl", "-w", f"{key}={value}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("  sysctl: %s = %s", key, value)
                return True
        except FileNotFoundError:
            pass  # sysctl not found — try /proc/sys/

        # Fallback: write directly to /proc/sys/<key> (dots → slashes)
        proc_path = "/proc/sys/" + key.replace(".", "/")
        try:
            with open(proc_path, "w") as f:
                f.write(value + "\n")
            logger.info("  /proc/sys: %s = %s", key, value)
            return True
        except (OSError, FileNotFoundError) as exc:
            logger.warning("  Failed to set %s=%s: %s", key, value, exc)
            return False

    def _set_cpu_governor(self, governor: str):
        """Set the CPU frequency governor across all online CPUs."""
        if _DRY_RUN:
            logger.info("[DRY RUN] cpupower frequency-set -g %s", governor)
            return

        # Try cpupower first (modern systems)
        try:
            result = subprocess.run(
                ["cpupower", "frequency-set", "-g", governor],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("  CPU governor: %s (via cpupower)", governor)
                return
        except FileNotFoundError:
            pass

        # Fallback: write to each CPU's scaling_governor file
        cpu_base = "/sys/devices/system/cpu"
        if not os.path.isdir(cpu_base):
            logger.warning("  CPU governor: /sys not available — skipping.")
            return

        set_count = 0
        for entry in os.listdir(cpu_base):
            if not entry.startswith("cpu") or not entry[3:].isdigit():
                continue
            gov_path = os.path.join(cpu_base, entry, "cpufreq", "scaling_governor")
            try:
                with open(gov_path, "w") as f:
                    f.write(governor + "\n")
                set_count += 1
            except OSError:
                pass

        if set_count > 0:
            logger.info("  CPU governor: %s (via sysfs, %d CPUs)", governor, set_count)
        else:
            logger.warning("  CPU governor: Could not set '%s' on any CPU.", governor)

    def _set_io_scheduler(self, scheduler: str):
        """Set the I/O scheduler for all rotational and NVMe block devices."""
        if _DRY_RUN:
            logger.info("[DRY RUN] I/O scheduler → %s", scheduler)
            return

        block_dir = "/sys/block"
        if not os.path.isdir(block_dir):
            logger.warning("  I/O scheduler: /sys/block not available — skipping.")
            return

        set_count = 0
        for device in os.listdir(block_dir):
            # Skip loop, ram, and zram devices
            if device.startswith(("loop", "ram", "zram")):
                continue
            sched_path = os.path.join(block_dir, device, "queue", "scheduler")
            try:
                with open(sched_path, "w") as f:
                    f.write(scheduler + "\n")
                set_count += 1
                logger.info("  I/O scheduler: %s → %s", device, scheduler)
            except OSError as exc:
                logger.debug("  I/O scheduler: %s skipped: %s", device, exc)

        if set_count == 0:
            logger.warning("  I/O scheduler: No block devices updated.")
