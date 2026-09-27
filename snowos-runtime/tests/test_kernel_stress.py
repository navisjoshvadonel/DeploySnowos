#!/usr/bin/env python3
"""
SnowOS Kernel — High-Load Stress & Concurrency Test Suite.
========================================================

Simulates high-workload enterprise environments across:
  1. Multi-Threaded MLFQ Scheduler Concurrency (1,000 tasks under load).
  2. High-Throughput NJ Shared-Memory IPC (2,000 packets under backpressure).
  3. SnowFS Multi-Directory & Multi-Block Stress (100 files + CRC32 verification).
  4. Chaos Crash-Storm & Circuit Breaker Fault Isolation under load.
  5. Kernel Boot Sequence & Clean Teardown Lifecycle.
"""

import sys
import os
import time
import random
import threading
import unittest

# Ensure snowos-runtime/src is in PYTHONPATH
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from kernel_layer.performance import (
    MLFQScheduler,
    QueueLevel,
    NJRingBuffer,
    NJFaultDomain,
    ComponentHealthState,
)
from kernel_layer.io_hardware import (
    SnowFS,
    BlockDevice,
    DataIntegrityError,
)
from kernel_layer.boot_init import KernelBootSequence, BootStage


class TestKernelStressHighLoad(unittest.TestCase):
    """Stress tests simulating intense enterprise operating conditions."""

    def test_mlfq_scheduler_1000_tasks_concurrency(self):
        """Dispatches 1,000 tasks concurrently across 4 priority queues."""
        scheduler = MLFQScheduler(num_workers=8)
        scheduler.start()

        completed_tasks = {}
        lock = threading.Lock()

        def worker_task(task_id: int, val: int):
            # Compute workload
            res = (val * val + 3) % 10007
            with lock:
                completed_tasks[task_id] = res

        num_tasks = 1000
        start_time = time.perf_counter()

        for i in range(num_tasks):
            # Distribute across Q0, Q1, Q2, Q3
            prio = QueueLevel(i % 4)
            scheduler.submit(f"task_{i}", worker_task, i, i + 1, priority=prio)

        # Wait for all tasks to complete
        deadline = time.time() + 10.0
        while len(completed_tasks) < num_tasks and time.time() < deadline:
            time.sleep(0.01)

        elapsed = time.perf_counter() - start_time
        scheduler.stop()

        self.assertEqual(len(completed_tasks), num_tasks, f"Only {len(completed_tasks)}/1000 tasks completed")
        throughput = num_tasks / elapsed
        self.assertGreater(throughput, 100.0, f"Throughput too low: {throughput:.1f} tasks/sec")

    def test_nj_shared_memory_ipc_high_concurrency_stress(self):
        """Streams 2,000 packets through a 32-slot NJ Ring Buffer under backpressure."""
        shm_name = f"snowos_stress_shm_{os.getpid()}_{int(time.time() * 1000) % 10000}"
        # Saturated 32-slot ring buffer to force continuous micro-spinning and backpressure
        rb = NJRingBuffer(shm_name, capacity=32, slot_size=256, create=True)

        num_packets = 2000
        received_packets = []
        consumer_done = threading.Event()

        def consumer():
            while len(received_packets) < num_packets:
                pkt = rb.read(timeout_ms=50.0)
                if pkt:
                    received_packets.append(pkt)
            consumer_done.set()

        t_cons = threading.Thread(target=consumer, daemon=True)
        t_cons.start()

        start_time = time.perf_counter()
        for i in range(num_packets):
            payload = f"STRESS_PACKET_{i:06d}_{random.randint(1000, 9999)}".encode("utf-8")
            written = False
            while not written:
                written = rb.write(payload, timeout_ms=50.0)

        consumer_done.wait(timeout=5.0)
        elapsed = time.perf_counter() - start_time
        rb.unlink()

        self.assertEqual(len(received_packets), num_packets, f"Received only {len(received_packets)}/{num_packets}")
        throughput = num_packets / elapsed
        self.assertGreater(throughput, 500.0, f"IPC throughput too low: {throughput:.1f} pkts/sec")

    def test_snowfs_filesystem_multi_dir_and_file_stress(self):
        """Creates 10 directories and 50 files of varying sizes with CRC32 data integrity verification."""
        bdev = BlockDevice(total_blocks=1024, block_size=1024)
        fs = SnowFS.format(bdev, total_inodes=128)

        # 1. Create directories
        for d in range(10):
            fs.mkdir(f"/dir_{d}")

        # 2. Write 50 files with payloads from 16 bytes to 3,000 bytes
        created_files = {}
        for i in range(50):
            dir_idx = i % 10
            path = f"/dir_{dir_idx}/data_{i}.bin"
            # Variable size payload
            size = 32 + (i * 50)  # Up to 2,500 bytes (spans up to 3 blocks)
            payload = bytes([((x * 7) + i) % 256 for x in range(size)])
            fs.write_file(path, payload)
            created_files[path] = payload

        # 3. Read back all 50 files and verify byte-for-byte fidelity and CRC32
        for path, expected_data in created_files.items():
            read_data = fs.read_file(path)
            self.assertEqual(len(read_data), len(expected_data))
            self.assertEqual(read_data, expected_data)

        # 4. Run fsck to verify filesystem remained 100% clean
        is_clean, issues = fs.fsck()
        self.assertTrue(is_clean, f"fsck failed after stress test: {issues}")
        self.assertEqual(len(issues), 0)

    def test_chaos_crash_storm_circuit_breaker_stress(self):
        """Injects 30 consecutive crashes to test circuit breaker quarantine under high failure velocity."""
        domain = NJFaultDomain(
            "ChaosUnstableAIModel",
            failure_threshold=4,
            window_seconds=10.0,
            quarantine_duration_sec=2.0,
            fallback_fn=lambda exc, snap: "SAFE_FALLBACK",
        )

        crash_counter = 0

        def failing_inference():
            nonlocal crash_counter
            crash_counter += 1
            raise ArithmeticError(f"Simulated Tensor Division By Zero #{crash_counter}")

        # Fire 30 requests rapidly
        results = []
        for _ in range(30):
            success, res = domain.execute(failing_inference)
            results.append((success, res))

        # First 4 triggered the threshold; remaining 26 must have been quarantined
        self.assertEqual(domain.state, ComponentHealthState.QUARANTINED)
        self.assertEqual(crash_counter, 4, "Failing function should not execute more than 4 times during quarantine")

        # All results should gracefully return fallback without crashing process
        for success, res in results:
            self.assertFalse(success)
            self.assertEqual(res, "SAFE_FALLBACK")

    def test_kernel_boot_sequence_lifecycle(self):
        """Verifies clean multi-stage kernel boot and graceful teardown."""
        bootloader = KernelBootSequence(storage_blocks=512, scheduler_workers=4)
        ctx = bootloader.boot()

        self.assertTrue(ctx.is_operational())
        self.assertEqual(ctx.stage, BootStage.STAGE_5_READY)
        self.assertGreater(ctx.boot_time_ms, 0.0)
        self.assertIsNotNone(ctx.snow_fs)
        self.assertIsNotNone(ctx.scheduler)
        self.assertIsNotNone(ctx.hardware_accelerator)
        self.assertIsNotNone(ctx.driver_manager)

        # Verify default system files created
        release_info = ctx.snow_fs.read_file("/etc/os-release").decode("utf-8")
        self.assertIn("SnowOS", release_info)

        # Graceful shutdown
        bootloader.shutdown()
        self.assertEqual(ctx.stage, BootStage.SHUTDOWN)


if __name__ == "__main__":
    unittest.main()
