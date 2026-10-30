"""
SnowOS Kernel Resource Manager — Comprehensive Resource Arbitration Engine.

Arbitrates CPU scheduling, memory budgeting, and concurrency controls
between core OS services and heavy AI workloads.
"""

from __future__ import annotations

import os
import psutil
import logging
from typing import Optional, Callable, Any, Tuple, List, Dict

from .smart_scheduler import MLFQScheduler, SchedTask, QueueLevel
from .memory_governor import AIMemoryGovernor, BufferPool
from .nj_engine import (
    NJAlgorithmSuite,
    NJRingBuffer,
    NJCoalescer,
    NJCoalesceEvent,
    EventPriority,
    NJFaultDomain,
)

logger = logging.getLogger("SnowOS.ResourceManager")


class ResourceManager:
    """Arbitrates CPU, memory, IPC, and fault domains between SnowOS modules."""

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

        # 4. NJ Performance & Stability Framework (Zero-copy IPC, Coalescer, Fault Domains)
        self.nj = NJAlgorithmSuite()

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

    # ─────────────────────────────────────────────────────────────────────────
    # NJ Performance & Stability Facade
    # ─────────────────────────────────────────────────────────────────────────

    def get_ipc_channel(
        self,
        name: str,
        capacity: int = 128,
        slot_size: int = 4096,
        create: bool = True
    ) -> NJRingBuffer:
        """Acquire a zero-copy NJ Shared Memory IPC Channel."""
        return self.nj.create_channel(name, capacity=capacity, slot_size=slot_size, create=create)

    def create_event_coalescer(
        self,
        name: str,
        callback: Callable[[List[NJCoalesceEvent]], None],
        burst_threshold_hz: float = 50.0
    ) -> NJCoalescer:
        """Acquire an NJ Adaptive Micro-Burst Coalescer."""
        return self.nj.create_coalescer(name, callback, burst_threshold_hz=burst_threshold_hz)

    def run_isolated(
        self,
        domain_name: str,
        target_fn: Callable[..., Any],
        *args,
        state_snapshot: Optional[Dict[str, Any]] = None,
        rollback_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
        fallback_fn: Optional[Callable[[Exception, Any], Any]] = None,
        failure_threshold: int = 3,
        **kwargs
    ) -> Tuple[bool, Any]:
        """
        Execute an unverified or AI task safely inside an NJ Fault Domain cage.
        Guarantees that crashes and memory faults will not freeze the host OS/daemon.
        """
        domain = self.nj.create_fault_domain(
            domain_name,
            failure_threshold=failure_threshold,
            fallback_fn=fallback_fn
        )
        return domain.execute(
            target_fn,
            *args,
            state_snapshot=state_snapshot,
            rollback_fn=rollback_fn,
            **kwargs
        )

    def shutdown(self):
        """Clean shutdown of background scheduling, compaction threads, and NJ engine."""
        self.scheduler.stop()
        self.nj.shutdown()
