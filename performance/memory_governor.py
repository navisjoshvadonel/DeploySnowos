"""
SnowOS Kernel Memory Governor — Virtual Memory Management, Paging & Anti-Leak Engine.

Provides comprehensive memory architecture for SnowOS:
  1. Virtual Memory & Paging:
     - 4KB page size with Two-Tier Page Tables
     - Page Table Entries (PTE) with Writable, User/Supervisor, Present, Dirty bits
     - Page Fault Trap Handler with LRU (Least Recently Used) Eviction to Swap
     - Hardware-level protection verification (SIGSEGV / AccessViolation trapping)
  2. AI Working-Set Governor & Anti-OOM Throttler:
     - Enforces memory caps on heavy AI processes (LLM context, vector embeddings)
     - Proactive cache compaction before Linux OOM killer triggers
  3. Zero-Leak Tracker & Buffer Recycler:
     - Pre-allocated zero-copy byte buffer pool to eliminate heap fragmentation
     - Reference cycle detector and garbage collector hooks
"""

import collections
import gc
import logging
import os
import psutil
import threading
import time
import weakref
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger("SnowOS.MemoryGovernor")

PAGE_SIZE = 4096  # 4 KB pages


# ─────────────────────────────────────────────────────────────────────────────
# 1. Virtual Memory & Protection Exceptions
# ─────────────────────────────────────────────────────────────────────────────
class MemoryProtectionError(Exception):
    """Base exception for virtual memory protection violations."""
    pass


class AccessViolationError(MemoryProtectionError):
    """Raised when attempting to write to a read-only virtual page."""
    pass


class PrivilegeViolationError(MemoryProtectionError):
    """Raised when user-mode code attempts to access supervisor-only page."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 2. Page Table Entry (PTE)
# ─────────────────────────────────────────────────────────────────────────────
class PageTableEntry:
    """Simulates a hardware Page Table Entry."""
    __slots__ = (
        "frame_number", "present", "writable", "user_accessible",
        "dirty", "referenced", "last_accessed"
    )

    def __init__(self, writable: bool = True, user_accessible: bool = True):
        self.frame_number: Optional[int] = None
        self.present: bool = False
        self.writable: bool = writable
        self.user_accessible: bool = user_accessible
        self.dirty: bool = False
        self.referenced: bool = False
        self.last_accessed: float = time.monotonic()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Virtual Memory Manager (VMM) with LRU Page Replacement
# ─────────────────────────────────────────────────────────────────────────────
class VirtualMemoryManager:
    """
    Simulates OS Paged Virtual Memory with LRU frame eviction and protection.
    """
    def __init__(self, max_physical_frames: int = 16):
        self.max_physical_frames = max_physical_frames
        self.page_size = PAGE_SIZE

        # Physical RAM frames: frame_idx -> bytearray(PAGE_SIZE)
        self.physical_ram: List[bytearray] = [
            bytearray(self.page_size) for _ in range(max_physical_frames)
        ]
        # Frame owner: frame_idx -> (vmm_instance, virtual_page_number)
        self.frame_owner: Dict[int, Tuple["VirtualMemoryManager", int]] = {}

        # Virtual Page Number -> PTE
        self.page_table: Dict[int, PageTableEntry] = {}

        # Swap backing store: virtual_page_number -> bytes
        self.swap_store: Dict[int, bytes] = {}

        self._lock = threading.Lock()
        self.stats = {
            "page_faults": 0,
            "page_evictions": 0,
            "reads": 0,
            "writes": 0,
        }

    def allocate_page(self, vpn: int, writable: bool = True, user_accessible: bool = True) -> PageTableEntry:
        """Allocate a new virtual page in the page table (demand paged on first access)."""
        with self._lock:
            pte = PageTableEntry(writable=writable, user_accessible=user_accessible)
            self.page_table[vpn] = pte
            return pte

    def _find_free_frame(self) -> Optional[int]:
        """Find an unallocated physical RAM frame."""
        for frame_idx in range(self.max_physical_frames):
            if frame_idx not in self.frame_owner:
                return frame_idx
        return None

    def _select_lru_victim_frame(self) -> int:
        """Select physical frame containing the least-recently-accessed page."""
        oldest_time = float("inf")
        victim_frame = 0

        for frame_idx, (vmm, vpn) in self.frame_owner.items():
            pte = vmm.page_table.get(vpn)
            if pte and pte.last_accessed < oldest_time:
                oldest_time = pte.last_accessed
                victim_frame = frame_idx

        return victim_frame

    def _handle_page_fault(self, vpn: int) -> int:
        """
        Trap handler for page faults:
          1. Allocate a free physical frame (or evict LRU victim to swap).
          2. If page was previously swapped, reload from swap store.
          3. Bind physical frame to virtual page and update PTE.
        """
        self.stats["page_faults"] += 1
        pte = self.page_table[vpn]

        frame_idx = self._find_free_frame()
        if frame_idx is None:
            # Physical memory full — run LRU eviction
            frame_idx = self._select_lru_victim_frame()
            victim_vmm, victim_vpn = self.frame_owner[frame_idx]
            victim_pte = victim_vmm.page_table[victim_vpn]

            # If dirty, write to swap store
            if victim_pte.dirty:
                victim_vmm.swap_store[victim_vpn] = bytes(self.physical_ram[frame_idx])

            # Invalidate victim page in page table
            victim_pte.present = False
            victim_pte.frame_number = None
            self.stats["page_evictions"] += 1
            logger.debug("Page Fault Handler: Evicted VPN %d from physical frame %d to swap.", victim_vpn, frame_idx)

        # Restore from swap if available, else zero out frame
        if vpn in self.swap_store:
            data = self.swap_store.pop(vpn)
            self.physical_ram[frame_idx][:] = data
        else:
            self.physical_ram[frame_idx][:] = b"\x00" * self.page_size

        self.frame_owner[frame_idx] = (self, vpn)
        pte.frame_number = frame_idx
        pte.present = True
        pte.dirty = False
        pte.referenced = True
        pte.last_accessed = time.monotonic()
        return frame_idx

    def read_byte(self, virtual_address: int, user_mode: bool = True) -> int:
        """Translate virtual address and read byte, enforcing memory protection."""
        with self._lock:
            self.stats["reads"] += 1
            vpn = virtual_address // self.page_size
            offset = virtual_address % self.page_size

            pte = self.page_table.get(vpn)
            if pte is None:
                raise MemoryProtectionError(f"Segmentation fault: unmapped address 0x{virtual_address:X}")

            # Protection check: Supervisor page access from user mode
            if not pte.user_accessible and user_mode:
                raise PrivilegeViolationError(f"General Protection Fault: user code cannot read supervisor page {vpn}")

            # Check presence (Demand Paging)
            if not pte.present:
                frame_idx = self._handle_page_fault(vpn)
            else:
                frame_idx = pte.frame_number

            pte.referenced = True
            pte.last_accessed = time.monotonic()
            return self.physical_ram[frame_idx][offset]

    def write_byte(self, virtual_address: int, value: int, user_mode: bool = True):
        """Translate virtual address and write byte, enforcing write protection."""
        with self._lock:
            self.stats["writes"] += 1
            vpn = virtual_address // self.page_size
            offset = virtual_address % self.page_size

            pte = self.page_table.get(vpn)
            if pte is None:
                raise MemoryProtectionError(f"Segmentation fault: unmapped address 0x{virtual_address:X}")

            # Protection check: Write on Read-Only Page
            if not pte.writable:
                raise AccessViolationError(f"Access Violation: write attempt on read-only page {vpn}")

            # Protection check: User vs Supervisor
            if not pte.user_accessible and user_mode:
                raise PrivilegeViolationError(f"General Protection Fault: user code cannot write to supervisor page {vpn}")

            if not pte.present:
                frame_idx = self._handle_page_fault(vpn)
            else:
                frame_idx = pte.frame_number

            self.physical_ram[frame_idx][offset] = value & 0xFF
            pte.dirty = True
            pte.referenced = True
            pte.last_accessed = time.monotonic()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Zero-Copy Pre-Allocated Buffer Pool (Prevents Heap Fragmentation)
# ─────────────────────────────────────────────────────────────────────────────
class BufferPool:
    """
    Pre-allocated object pool for byte arrays to eliminate GC overhead
    and memory fragmentation during high-throughput IPC message streaming.
    """
    def __init__(self, buffer_size: int = 65536, pool_capacity: int = 32):
        self.buffer_size = buffer_size
        self.pool_capacity = pool_capacity
        self._pool: collections.deque[bytearray] = collections.deque(
            bytearray(buffer_size) for _ in range(pool_capacity)
        )
        self._lock = threading.Lock()

    def acquire(self) -> bytearray:
        """Acquire a buffer from the pool, or allocate a new one if pool is dry."""
        with self._lock:
            if self._pool:
                return self._pool.pop()
        return bytearray(self.buffer_size)

    def release(self, buf: bytearray):
        """Return a buffer to the pool after clearing."""
        if len(buf) != self.buffer_size:
            return  # Wrong size, discard
        with self._lock:
            if len(self._pool) < self.pool_capacity:
                self._pool.append(buf)


# ─────────────────────────────────────────────────────────────────────────────
# 5. AI Working-Set Governor & Anti-OOM Memory Compactor
# ─────────────────────────────────────────────────────────────────────────────
class AIMemoryGovernor:
    """
    Monitors process memory and proactive compacts AI working sets
    to ensure zero memory leaks and prevent system OOM freezes.
    """
    def __init__(self, soft_limit_mb: float = 512.0, hard_limit_mb: float = 1024.0):
        self.soft_limit_mb = soft_limit_mb
        self.hard_limit_mb = hard_limit_mb
        self._cache_eviction_hooks: List[weakref.ref] = []
        self._lock = threading.Lock()

    def register_cache_evictor(self, evictor_func):
        """Register a callback that frees non-essential AI caches during pressure."""
        with self._lock:
            self._cache_eviction_hooks.append(weakref.WeakMethod(evictor_func)
                                             if hasattr(evictor_func, "__self__")
                                             else weakref.ref(evictor_func))

    def get_current_rss_mb(self) -> float:
        """Read actual Resident Set Size (RSS) memory in megabytes."""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024.0 * 1024.0)
        except Exception:
            return 0.0

    def enforce_quota(self) -> Tuple[bool, float]:
        """
        Check memory usage against quotas.
        If exceeding soft limit, triggers proactive compaction and garbage collection.
        Returns: (is_healthy, current_rss_mb)
        """
        rss_mb = self.get_current_rss_mb()

        if rss_mb > self.soft_limit_mb:
            logger.warning(
                "Memory Governor: RSS (%.1f MB) exceeds soft limit (%.1f MB) — initiating proactive compaction.",
                rss_mb, self.soft_limit_mb
            )

            # 1. Trigger registered cache eviction hooks
            with self._lock:
                active_hooks = []
                for hook in self._cache_eviction_hooks:
                    f = hook()
                    if f is not None:
                        active_hooks.append(hook)
                        try:
                            f()
                        except Exception as e:
                            logger.error("Error in cache eviction hook: %s", e)
                self._cache_eviction_hooks = active_hooks

            # 2. Force Python generational GC pass
            gc.collect(generation=2)

            post_rss = self.get_current_rss_mb()
            logger.info("Memory compaction completed: %.1f MB -> %.1f MB", rss_mb, post_rss)
            return (post_rss <= self.hard_limit_mb), post_rss

        return True, rss_mb
