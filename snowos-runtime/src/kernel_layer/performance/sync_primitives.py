"""
SnowOS Kernel Synchronization Primitives — High-Performance Concurrency Engine.

Provides rock-solid synchronization primitives for the SnowOS kernel and daemons:
  1. DeadlockDetectingMutex: Fair reentrant mutex with cycle-detection in the
     Resource Allocation Graph (RAG) to prevent deadlocks before they happen.
  2. AdaptiveSpinlock: Dual-phase hybrid spinlock with low-latency user-space
     busy-spin for short-held critical sections and futex/event sleep fallback.
  3. FairCountingSemaphore: FIFO-ordered queue semaphore preventing thread starvation.
  4. FairRWLock: Read-write lock with writer-preference preventing writer starvation.
"""

import threading
import time
import collections
import logging
from typing import Dict, Set, Optional, List

logger = logging.getLogger("SnowOS.SyncPrimitives")


class SynchronizationError(Exception):
    """Base exception for kernel synchronization errors."""
    pass


class DeadlockDetectedException(SynchronizationError):
    """Raised when acquiring a mutex would cause a circular wait deadlock."""
    def __init__(self, thread_id: int, lock_id: str, cycle: List[str]):
        self.thread_id = thread_id
        self.lock_id = lock_id
        self.cycle = cycle
        super().__init__(
            f"DEADLOCK PREVENTED: Thread {thread_id} attempting to acquire '{lock_id}' "
            f"would cause circular dependency: {' -> '.join(cycle)}"
        )


class LockTimeoutException(SynchronizationError):
    """Raised when lock acquisition exceeds the specified timeout."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 1. Global Resource Allocation Graph (RAG) for Deadlock Prevention
# ─────────────────────────────────────────────────────────────────────────────
class _ResourceAllocationGraph:
    """
    Maintains the global wait-for graph:
      - Thread -> Lock it is waiting for
      - Lock -> Thread that owns it
      - Thread -> Set of locks it currently holds
    """
    _instance = None
    _rag_lock = threading.Lock()

    def __init__(self):
        # thread_id -> lock_id (what lock is this thread blocked on)
        self.waiting_for: Dict[int, str] = {}
        # lock_id -> thread_id (who owns this lock)
        self.lock_owner: Dict[str, int] = {}
        # thread_id -> set of lock_ids (all locks held by this thread)
        self.held_locks: Dict[int, Set[str]] = collections.defaultdict(set)

    @classmethod
    def get(cls) -> "_ResourceAllocationGraph":
        if cls._instance is None:
            with cls._rag_lock:
                if cls._instance is None:
                    cls._instance = _ResourceAllocationGraph()
        return cls._instance

    def would_deadlock(self, thread_id: int, lock_id: str) -> Optional[List[str]]:
        """
        Check if thread_id waiting for lock_id creates a cycle in the wait-for graph.
        Returns the cycle chain if a deadlock would occur, or None if safe.
        """
        with self._rag_lock:
            owner = self.lock_owner.get(lock_id)
            if owner is None or owner == thread_id:
                return None  # Lock is free or re-entrant acquire

            # Follow the wait-for chain:
            # Current thread wants lock_id, owned by `owner`.
            # If `owner` is waiting for a lock owned by thread_id, or transitively...
            visited_threads = [thread_id]
            curr_thread = owner

            while curr_thread is not None:
                if curr_thread == thread_id:
                    # Cycle detected! Reconstruct the lock/thread chain
                    cycle_nodes = [f"Thread-{t}" for t in visited_threads] + [f"Thread-{thread_id}"]
                    return cycle_nodes

                visited_threads.append(curr_thread)
                # What is curr_thread waiting for?
                blocked_on_lock = self.waiting_for.get(curr_thread)
                if not blocked_on_lock:
                    break
                curr_thread = self.lock_owner.get(blocked_on_lock)

            return None

    def register_wait(self, thread_id: int, lock_id: str):
        with self._rag_lock:
            self.waiting_for[thread_id] = lock_id

    def unregister_wait(self, thread_id: int):
        with self._rag_lock:
            self.waiting_for.pop(thread_id, None)

    def register_acquired(self, thread_id: int, lock_id: str):
        with self._rag_lock:
            self.waiting_for.pop(thread_id, None)
            self.lock_owner[lock_id] = thread_id
            self.held_locks[thread_id].add(lock_id)

    def register_released(self, thread_id: int, lock_id: str):
        with self._rag_lock:
            if self.lock_owner.get(lock_id) == thread_id:
                self.lock_owner.pop(lock_id, None)
            if thread_id in self.held_locks:
                self.held_locks[thread_id].discard(lock_id)
                if not self.held_locks[thread_id]:
                    self.held_locks.pop(thread_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Deadlock-Detecting Fair Mutex
# ─────────────────────────────────────────────────────────────────────────────
class DeadlockDetectingMutex:
    """
    Reentrant Mutex equipped with runtime circular wait (deadlock) prevention.
    Throws DeadlockDetectedException immediately if acquiring would cause a freeze.
    """
    _counter = 0
    _cls_lock = threading.Lock()

    def __init__(self, name: Optional[str] = None):
        with self._cls_lock:
            DeadlockDetectingMutex._counter += 1
            idx = DeadlockDetectingMutex._counter
        self.lock_id = name or f"Mutex-{idx}"
        self._owner: Optional[int] = None
        self._count = 0
        self._inner_lock = threading.Lock()
        self._waiters_cond = threading.Condition(self._inner_lock)
        self._rag = _ResourceAllocationGraph.get()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        tid = threading.get_ident()

        # Reentrant case: thread already owns this lock
        with self._inner_lock:
            if self._owner == tid:
                self._count += 1
                return True

        # Check for deadlock BEFORE waiting
        cycle = self._rag.would_deadlock(tid, self.lock_id)
        if cycle:
            raise DeadlockDetectedException(tid, self.lock_id, cycle)

        self._rag.register_wait(tid, self.lock_id)
        start_time = time.monotonic()

        with self._inner_lock:
            while self._owner is not None:
                remaining = None
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        self._rag.unregister_wait(tid)
                        raise LockTimeoutException(f"Timed out acquiring {self.lock_id}")

                self._waiters_cond.wait(timeout=remaining)

            # Acquired!
            self._owner = tid
            self._count = 1
            self._rag.register_acquired(tid, self.lock_id)
            return True

    def release(self):
        tid = threading.get_ident()
        with self._inner_lock:
            if self._owner != tid:
                raise SynchronizationError(f"Illegal release of {self.lock_id}: held by {self._owner}, caller is {tid}")
            self._count -= 1
            if self._count == 0:
                self._owner = None
                self._rag.register_released(tid, self.lock_id)
                self._waiters_cond.notify(1)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Adaptive Spinlock
# ─────────────────────────────────────────────────────────────────────────────
class AdaptiveSpinlock:
    """
    Hybrid Spinlock for ultra-low latency critical sections.
    Spins in user-space for up to `spin_limit` cycles before falling back
    to kernel event-based sleep to conserve CPU power under heavy contention.
    """
    def __init__(self, spin_limit: int = 128):
        self._spin_limit = spin_limit
        self._locked = False
        self._gate = threading.Lock()
        self._sleep_event = threading.Event()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        start_time = time.monotonic()

        # Phase 1: Fast user-space spin-wait
        for _ in range(self._spin_limit):
            with self._gate:
                if not self._locked:
                    self._locked = True
                    self._sleep_event.clear()
                    return True
            time.sleep(0)  # Pause instruction / yield time quantum slice

        # Phase 2: Fallback to event wait (no busy spin burning CPU)
        while True:
            with self._gate:
                if not self._locked:
                    self._locked = True
                    self._sleep_event.clear()
                    return True

            remaining = None
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    return False

            self._sleep_event.wait(timeout=remaining if remaining is not None else 0.05)

    def release(self):
        with self._gate:
            if not self._locked:
                raise SynchronizationError("Attempted to release unlocked AdaptiveSpinlock")
            self._locked = False
            self._sleep_event.set()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Fair Counting & Binary Semaphore (FIFO Starvation-Free)
# ─────────────────────────────────────────────────────────────────────────────
class FairCountingSemaphore:
    """
    Strict FIFO Counting Semaphore.
    Guarantees thread ordering so that threads waiting the longest acquire first,
    eliminating thread starvation completely under heavy AI workloads.
    """
    def __init__(self, value: int = 1):
        if value < 0:
            raise ValueError("Initial semaphore value must be >= 0")
        self._value = value
        self._lock = threading.Lock()
        # Deque of (Event, tid) to ensure strict FIFO wake-up order
        self._waiters: collections.deque[threading.Event] = collections.deque()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        with self._lock:
            # Fast path: slot is available and no one is ahead in line
            if self._value > 0 and not self._waiters:
                self._value -= 1
                return True

            # Must wait: enqueue our personal event
            my_event = threading.Event()
            self._waiters.append(my_event)

        start = time.monotonic()
        acquired = False
        try:
            while True:
                remaining = None
                if timeout is not None:
                    elapsed = time.monotonic() - start
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        break

                if my_event.wait(timeout=remaining if remaining is not None else 0.1):
                    acquired = True
                    break
        finally:
            if not acquired:
                with self._lock:
                    try:
                        self._waiters.remove(my_event)
                    except ValueError:
                        # If we were woken up right as timeout hit, return the token
                        self._value += 1
                        self._wake_next()

        return acquired

    def release(self):
        with self._lock:
            self._value += 1
            self._wake_next()

    def _wake_next(self):
        """Wake the earliest queued waiter if a slot is available."""
        if self._value > 0 and self._waiters:
            self._value -= 1
            earliest = self._waiters.popleft()
            earliest.set()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Fair Read-Write Lock (RWLock with Writer-Preference)
# ─────────────────────────────────────────────────────────────────────────────
class FairRWLock:
    """
    Reader-Writer Lock with Writer-Preference.
    Allows concurrent reads, but queues incoming readers as soon as a writer
    requests access. This prevents readers from infinitely starving writers.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._readers_ok = threading.Condition(self._lock)
        self._writer_ok = threading.Condition(self._lock)

        self._active_readers = 0
        self._waiting_writers = 0
        self._writer_active = False

    def acquire_read(self, timeout: Optional[float] = None) -> bool:
        start = time.monotonic()
        with self._lock:
            # Wait as long as a writer is active OR writers are waiting
            while self._writer_active or self._waiting_writers > 0:
                remaining = None
                if timeout is not None:
                    elapsed = time.monotonic() - start
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return False
                self._readers_ok.wait(timeout=remaining)

            self._active_readers += 1
            return True

    def release_read(self):
        with self._lock:
            if self._active_readers <= 0:
                raise SynchronizationError("release_read called with 0 active readers")
            self._active_readers -= 1
            if self._active_readers == 0 and self._waiting_writers > 0:
                # Last reader notifies waiting writer
                self._writer_ok.notify(1)

    def acquire_write(self, timeout: Optional[float] = None) -> bool:
        start = time.monotonic()
        with self._lock:
            self._waiting_writers += 1
            try:
                while self._writer_active or self._active_readers > 0:
                    remaining = None
                    if timeout is not None:
                        elapsed = time.monotonic() - start
                        remaining = timeout - elapsed
                        if remaining <= 0:
                            return False
                    self._writer_ok.wait(timeout=remaining)

                self._writer_active = True
                return True
            finally:
                self._waiting_writers -= 1

    def release_write(self):
        with self._lock:
            if not self._writer_active:
                raise SynchronizationError("release_write called without active writer")
            self._writer_active = False

            # If another writer is waiting, give it priority
            if self._waiting_writers > 0:
                self._writer_ok.notify(1)
            else:
                # Otherwise let all waiting readers proceed
                self._readers_ok.notify_all()

    class _ReadContext:
        def __init__(self, rwlock): self.rwlock = rwlock
        def __enter__(self): self.rwlock.acquire_read()
        def __exit__(self, exc_type, exc_val, exc_tb): self.rwlock.release_read()

    class _WriteContext:
        def __init__(self, rwlock): self.rwlock = rwlock
        def __enter__(self): self.rwlock.acquire_write()
        def __exit__(self, exc_type, exc_val, exc_tb): self.rwlock.release_write()

    def read_lock(self):
        return self._ReadContext(self)

    def write_lock(self):
        return self._WriteContext(self)
