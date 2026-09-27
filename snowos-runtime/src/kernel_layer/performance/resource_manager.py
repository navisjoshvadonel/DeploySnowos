"""
SnowOS Kernel Resource Manager — Comprehensive Resource Arbitration Engine.

Arbitrates CPU scheduling, memory budgeting, and concurrency controls
between core OS services and heavy AI workloads.
"""

import os
import psutil
import logging
from typing import Optional, Callable, Any, Tuple

from .smart_scheduler import MLFQScheduler, SchedTask, QueueLevel
from .memory_governor import AIMemoryGovernor, BufferPool

logger = logging.getLogger("SnowOS.ResourceManager")


class ResourceManager:
    """Arbitrates CPU and memory resource allocation between SnowOS modules."""

    def __init__(self, profiler=None, num_workers: int = 4):
        self.profiler = profiler
        self.logger = logger

        # 1. Multi-Level Feedback Queue Smart Scheduler
        self.scheduler = MLFQScheduler(num_workers=num_workers)
        self.scheduler.start()

        # 2. AI Working-Set Governor (512MB soft limit, 1024MB hard limit)
        self.memory_governor = AIMemoryGovernor(soft_limit_mb=512.0, hard_limit_mb=1024.0)

        # 3. IPC Zero-Copy Buffer Pool (64KB chunks)
        self.buffer_pool = BufferPool(buffer_size=65536, pool_capacity=32)

        self.priority_map = {
            "critical": -15, # System stability / Input
            "high": -10,     # Active UI / Shell
            "normal": 0,     # General AI Reasoning
            "low": 10,       # Background Learning
            "idle": 19       # Housekeeping / Cleanup
        }

    def schedule_task(
        self,
        name: str,
        func: Callable[..., Any],
        *args,
        priority: QueueLevel = QueueLevel.Q2_STANDARD,
        **kwargs
    ) -> SchedTask:
        """Schedule work on the kernel MLFQ scheduler."""
        return self.scheduler.submit(name, func, *args, priority=priority, **kwargs)

    def check_and_compact_memory(self) -> Tuple[bool, float]:
        """Proactively monitor memory consumption and compact if under pressure."""
        return self.memory_governor.enforce_quota()

    def get_policy(self, system_health: dict) -> str:
        """Determine resource policy based on current health."""
        cpu = system_health.get("cpu", 0)
        ram = system_health.get("ram", 0)

        if cpu > 90 or ram > 95:
            return "critical_only"
        elif cpu > 70:
            return "throttled"
        else:
            return "full_autonomy"

    def apply_priority(self, module_name: str, level: str):
        """Attempt to set the process priority for a module."""
        priority = self.priority_map.get(level, 0)
        try:
            p = psutil.Process(os.getpid())
            if priority >= 0:
                p.nice(priority)
                self.logger.info("Resource: Set '%s' to %s priority (nice: %d)", module_name, level, priority)
        except Exception as e:
            self.logger.debug("Priority adjustment failed: %s", e)

    def get_throttle_limit(self, mode: str) -> float:
        """Returns the delay (in seconds) to inject between non-critical tasks."""
        if mode == "critical_only":
            return 2.0
        elif mode == "throttled":
            return 0.5
        return 0.0

    def shutdown(self):
        """Clean shutdown of background scheduling and compaction threads."""
        self.scheduler.stop()
