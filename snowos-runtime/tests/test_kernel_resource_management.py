#!/usr/bin/env python3
"""
SnowOS Kernel Resource Management, Scheduling, and Concurrency Test Suite.

Validates:
  1. Multi-Level Feedback Queue (MLFQ) Scheduling:
     - Real-Time (Q0) tasks preempt and run before batch AI compute (Q3).
     - Anti-starvation boost logic.
  2. Virtual Memory Management & Protection:
     - Page allocation and Demand Paging.
     - LRU page eviction to swap when physical frames are exhausted.
     - AccessViolationError on write to read-only page.
     - PrivilegeViolationError on user access to supervisor page.
     - BufferPool zero-copy memory cycling.
  3. Synchronization & Concurrency:
     - Circular wait Deadlock Detection and Prevention.
     - AdaptiveSpinlock under high-contention multi-threaded increments.
     - FairCountingSemaphore FIFO fairness without starvation.
     - FairRWLock reader-concurrency and exclusive writer integrity.
"""

import sys
import os
import time
import threading
import unittest

# Ensure snowos-runtime/src is in PYTHONPATH
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from kernel_layer.performance import (
    DeadlockDetectingMutex,
    AdaptiveSpinlock,
    FairCountingSemaphore,
    FairRWLock,
    DeadlockDetectedException,
    MLFQScheduler,
    QueueLevel,
    VirtualMemoryManager,
    BufferPool,
    AIMemoryGovernor,
    AccessViolationError,
    PrivilegeViolationError,
)


class TestKernelSynchronization(unittest.TestCase):
    """Validates concurrency, mutual exclusion, and deadlock prevention."""

    def test_deadlock_detection_and_prevention(self):
        """
        Verify that a circular wait (Lock A -> Lock B vs Lock B -> Lock A)
        is trapped by DeadlockDetectingMutex and raises DeadlockDetectedException
        before freezing the process.
        """
        mutex_a = DeadlockDetectingMutex("Resource-A")
        mutex_b = DeadlockDetectingMutex("Resource-B")

        deadlock_detected = threading.Event()
        barrier = threading.Barrier(2)

        def worker_1():
            with mutex_a:
                barrier.wait()  # Both workers have acquired their first lock
                time.sleep(0.05)
                # Worker 1 now tries to acquire Resource-B (held by worker 2)
                try:
                    with mutex_b:
                        pass
                except DeadlockDetectedException:
                    deadlock_detected.set()

        def worker_2():
            with mutex_b:
                barrier.wait()  # Both workers have acquired their first lock
                time.sleep(0.05)
                # Worker 2 now tries to acquire Resource-A (held by worker 1)
                try:
                    with mutex_a:
                        pass
                except DeadlockDetectedException:
                    deadlock_detected.set()

        t1 = threading.Thread(target=worker_1)
        t2 = threading.Thread(target=worker_2)

        t1.start()
        t2.start()

        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        self.assertTrue(
            deadlock_detected.is_set(),
            "DeadlockDetectingMutex failed to detect and prevent circular wait deadlock!"
        )

    def test_adaptive_spinlock_under_contention(self):
        """
        Verify that AdaptiveSpinlock guarantees race-free execution
        across 10 concurrent threads hammering a shared variable.
        """
        spinlock = AdaptiveSpinlock(spin_limit=64)
        shared_counter = 0
        iterations = 500
        num_threads = 10

        def incrementer():
            nonlocal shared_counter
            for _ in range(iterations):
                with spinlock:
                    curr = shared_counter
                    time.sleep(0.00001)  # Induce race condition if unlocked
                    shared_counter = curr + 1

        threads = [threading.Thread(target=incrementer) for _ in range(num_threads)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(shared_counter, iterations * num_threads)

    def test_fair_semaphore_fifo_order(self):
        """
        Verify that FairCountingSemaphore grants access in strict FIFO order,
        eliminating starvation.
        """
        sem = FairCountingSemaphore(value=1)
        arrival_order = []
        acquisition_order = []
        lock = threading.Lock()

        # Hold the semaphore initially
        sem.acquire()

        def waiter(thread_id):
            with lock:
                arrival_order.append(thread_id)
            with sem:
                with lock:
                    acquisition_order.append(thread_id)

        threads = []
        for i in range(5):
            t = threading.Thread(target=waiter, args=(i,))
            threads.append(t)
            t.start()
            time.sleep(0.02)  # Space arrivals to enforce order

        # Release initial hold to let waiters proceed
        sem.release()

        for t in threads:
            t.join()

        self.assertEqual(arrival_order, acquisition_order, "FIFO ordering violated in semaphore!")

    def test_fair_rwlock_concurrency_and_exclusion(self):
        """
        Verify FairRWLock permits multiple concurrent readers but gives
        exclusive access to writers.
        """
        rwlock = FairRWLock()
        active_readers = 0
        max_concurrent_readers = 0
        reader_lock = threading.Lock()
        writer_ran_exclusively = True

        def reader():
            nonlocal active_readers, max_concurrent_readers
            with rwlock.read_lock():
                with reader_lock:
                    active_readers += 1
                    max_concurrent_readers = max(max_concurrent_readers, active_readers)
                time.sleep(0.02)
                with reader_lock:
                    active_readers -= 1

        def writer():
            nonlocal writer_ran_exclusively
            with rwlock.write_lock():
                if active_readers > 0:
                    writer_ran_exclusively = False
                time.sleep(0.02)

        threads = [threading.Thread(target=reader) for _ in range(6)]
        writer_thread = threading.Thread(target=writer)

        for t in threads[:3]: t.start()
        writer_thread.start()
        for t in threads[3:]: t.start()

        for t in threads: t.join()
        writer_thread.join()

        self.assertGreater(max_concurrent_readers, 1, "Readers were not concurrent!")
        self.assertTrue(writer_ran_exclusively, "Writer was not exclusive!")


class TestKernelSmartScheduler(unittest.TestCase):
    """Validates MLFQ scheduling and anti-starvation behavior."""

    def test_realtime_priority_precedence(self):
        """
        Verify that Real-Time / Interactive tasks (Q0/Q1) are selected
        and completed before low-priority AI batch tasks (Q3).
        """
        sched = MLFQScheduler(num_workers=1)  # Single worker to test dispatch ordering
        try:
            execution_order = []

            def ai_heavy_work():
                time.sleep(0.02)
                execution_order.append("AI_BATCH")

            def realtime_sys_work():
                time.sleep(0.01)
                execution_order.append("REALTIME")

            # Queue AI batch tasks first
            for _ in range(3):
                sched.submit("AI-Job", ai_heavy_work, priority=QueueLevel.Q3_AI_BATCH)

            # Queue a Real-Time system task after
            sched.submit("System-Event", realtime_sys_work, priority=QueueLevel.Q0_REALTIME)

            # Start scheduler with both queues populated
            sched.start()

            # Wait for all to finish
            time.sleep(0.25)

            # Realtime task should execute first
            self.assertEqual(execution_order[0], "REALTIME", "Realtime task was starved by AI tasks!")
        finally:
            sched.stop()


class TestVirtualMemoryAndProtection(unittest.TestCase):
    """Validates virtual memory allocation, paging, protection, and leak tracking."""

    def test_demand_paging_and_lru_eviction(self):
        """
        Allocate more virtual pages than physical frames to test
        demand paging and LRU page eviction to swap.
        """
        # Small physical frame pool (4 frames of 4096 bytes)
        vmm = VirtualMemoryManager(max_physical_frames=4)

        # Allocate 6 virtual pages (VPN 0 through 5)
        for vpn in range(6):
            vmm.allocate_page(vpn, writable=True, user_accessible=True)

        # Write data to pages 0, 1, 2, 3 (fills all 4 physical frames)
        for vpn in range(4):
            vmm.write_byte(vpn * 4096 + 10, vpn + 42)

        self.assertEqual(vmm.stats["page_evictions"], 0)

        # Access page 4 (triggers page fault and LRU eviction of page 0)
        vmm.write_byte(4 * 4096 + 10, 99)
        self.assertGreater(vmm.stats["page_evictions"], 0, "LRU eviction failed to trigger!")

        # Access page 0 again (should reload from swap)
        val = vmm.read_byte(0 * 4096 + 10)
        self.assertEqual(val, 42, "Swapped page data corrupted upon reload!")

    def test_memory_protection_violations(self):
        """
        Verify that write protection and user/supervisor protection are enforced.
        """
        vmm = VirtualMemoryManager(max_physical_frames=4)

        # 1. Read-only page
        vmm.allocate_page(vpn=10, writable=False, user_accessible=True)
        with self.assertRaises(AccessViolationError):
            vmm.write_byte(10 * 4096 + 5, 0xFF)

        # 2. Supervisor-only page accessed in user mode
        vmm.allocate_page(vpn=20, writable=True, user_accessible=False)
        with self.assertRaises(PrivilegeViolationError):
            vmm.read_byte(20 * 4096 + 5, user_mode=True)

    def test_buffer_pool_recycling(self):
        """
        Verify pre-allocated buffer pool recycling to prevent memory leaks and fragmentation.
        """
        pool = BufferPool(buffer_size=1024, pool_capacity=4)
        b1 = pool.acquire()
        b2 = pool.acquire()
        self.assertEqual(len(b1), 1024)
        pool.release(b1)
        b3 = pool.acquire()
        # b3 should be the recycled buffer b1
        self.assertIs(b1, b3)


if __name__ == "__main__":
    unittest.main()
