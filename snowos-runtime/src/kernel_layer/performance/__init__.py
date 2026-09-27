"""
SnowOS Kernel Performance & Resource Management Subsystem.
"""

from .sync_primitives import (
    DeadlockDetectingMutex,
    AdaptiveSpinlock,
    FairCountingSemaphore,
    FairRWLock,
    DeadlockDetectedException,
    LockTimeoutException,
    SynchronizationError,
)

from .smart_scheduler import (
    MLFQScheduler,
    SchedTask,
    QueueLevel,
)

from .memory_governor import (
    VirtualMemoryManager,
    PageTableEntry,
    AIMemoryGovernor,
    BufferPool,
    MemoryProtectionError,
    AccessViolationError,
    PrivilegeViolationError,
)

__all__ = [
    "DeadlockDetectingMutex",
    "AdaptiveSpinlock",
    "FairCountingSemaphore",
    "FairRWLock",
    "DeadlockDetectedException",
    "LockTimeoutException",
    "SynchronizationError",
    "MLFQScheduler",
    "SchedTask",
    "QueueLevel",
    "VirtualMemoryManager",
    "PageTableEntry",
    "AIMemoryGovernor",
    "BufferPool",
    "MemoryProtectionError",
    "AccessViolationError",
    "PrivilegeViolationError",
]
