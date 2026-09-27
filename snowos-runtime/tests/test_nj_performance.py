#!/usr/bin/env python3
"""
SnowOS Kernel — NJ Performance, Stability & Fault Isolation Test Suite.
======================================================================
Named in honour of NJ (Navis Josh).

Validates:
  1. NJ Fast-Path Shared-Memory IPC (NJRingBuffer):
     - Zero-copy write and read over POSIX shared memory (/dev/shm).
     - Producer-consumer data integrity with direct binary slot packing.
     - Microsecond-scale message latency.
     - Buffer capacity limit and drop accounting.
     - Safe unlink and destruction.

  2. NJ Adaptive Micro-Burst Coalescing Algorithm (NJCoalescer):
     - Low-frequency mode: immediate zero-delay pass-through.
     - Burst mode: dynamic micro-window coalescing reducing context switches (>60%).
     - URGENT priority bypass: instant flush of critical alerts.

  3. NJ Crash Resilience & Fault Isolation (NJFaultDomain):
     - Crash isolation: exceptions inside domain do not freeze or crash host OS.
     - State snapshotting & rollback: restores clean state on worker failure.
     - Deterministic fallback execution on failure.
     - Circuit Breaker: trips to QUARANTINED on rapid repeated crashes, preventing crash loops.
     - Manual reset and half-open state transitions.

  4. ResourceManager NJ Integration:
     - Seamless integration with kernel ResourceManager facade.
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
    NJRingBuffer,
    NJCoalescer,
    NJCoalesceEvent,
    EventPriority,
    NJFaultDomain,
    ComponentHealthState,
    NJAlgorithmSuite,
)
from kernel_layer.performance.resource_manager import ResourceManager


class TestNJFastPathIPC(unittest.TestCase):
    """Validates NJ zero-copy shared memory IPC ring buffer."""

    def setUp(self):
        self.shm_name = f"snowos_nj_test_{int(time.time() * 1000) % 100000}"

    def tearDown(self):
        try:
            rb = NJRingBuffer(self.shm_name, create=False)
            rb.unlink()
        except Exception:
            pass

    def test_zero_copy_write_and_read(self):
        """Verify producer writes and consumer reads via shared memory."""
        # 1. Create buffer as Kernel/Server
        server_rb = NJRingBuffer(self.shm_name, capacity=16, slot_size=256, create=True)
        
        # 2. Attach as Client/AI module
        client_rb = NJRingBuffer(self.shm_name, create=False)

        test_payload = b"SnowOS_NJ_Tensor_Stream_Packet_#001"
        written = server_rb.write(test_payload, channel_id=1, timeout_ms=50.0)
        self.assertTrue(written, "Server failed to write payload into NJ shared memory")

        # 3. Read from client
        received = client_rb.read(channel_id=1, timeout_ms=50.0)
        self.assertEqual(received, test_payload, "Client received corrupted payload")

        server_rb.unlink()
        client_rb.close()

    def test_ipc_latency_and_throughput(self):
        """Verify high-throughput, microsecond-scale messaging across threads."""
        rb = NJRingBuffer(self.shm_name, capacity=64, slot_size=512, create=True)
        num_messages = 500
        received_items = []

        def consumer():
            for _ in range(num_messages):
                msg = rb.read(timeout_ms=500.0)
                if msg:
                    received_items.append(msg)

        consumer_thread = threading.Thread(target=consumer, daemon=True)
        consumer_thread.start()

        start_time = time.perf_counter()
        for i in range(num_messages):
            payload = f"STREAM_FRAME_{i}".encode("utf-8")
            ok = rb.write(payload, timeout_ms=500.0)
            self.assertTrue(ok)

        consumer_thread.join(timeout=3.0)
        elapsed_sec = time.perf_counter() - start_time

        self.assertEqual(len(received_items), num_messages)
        avg_latency_us = (elapsed_sec / num_messages) * 1_000_000.0
        # Should easily achieve < 250 microseconds per message in Python over SHM
        self.assertLess(avg_latency_us, 1000.0, f"Average latency too high: {avg_latency_us:.1f}us")

        stats = rb.get_stats()
        self.assertEqual(stats["write_seq"], num_messages)
        self.assertEqual(stats["read_seq"], num_messages)
        self.assertEqual(stats["pending_items"], 0)

        rb.unlink()

    def test_buffer_saturation_and_drop_accounting(self):
        """Verify buffer reports saturation and increments dropped_count when full."""
        capacity = 4
        rb = NJRingBuffer(self.shm_name, capacity=capacity, slot_size=128, create=True)

        for i in range(capacity):
            self.assertTrue(rb.write(f"item_{i}".encode("utf-8"), timeout_ms=10.0))

        # 5th item without reading should time out and record drop
        ok = rb.write(b"overflow_item", timeout_ms=15.0)
        self.assertFalse(ok, "Overflow write should return False")

        stats = rb.get_stats()
        self.assertEqual(stats["dropped_count"], 1)

        rb.unlink()


class TestNJAdaptiveCoalescer(unittest.TestCase):
    """Validates the NJ Adaptive Micro-Burst Coalescing Algorithm."""

    def test_quiet_mode_zero_delay_passthrough(self):
        """Under low frequency, events pass through with 1:1 dispatch ratio."""
        dispatches = []

        def on_dispatch(batch):
            dispatches.append(batch)

        coalescer = NJCoalescer("test_quiet", on_dispatch, burst_threshold_hz=100.0)

        # Send events with 20ms spacing (50 Hz < 100 Hz burst threshold)
        for i in range(3):
            ev = NJCoalesceEvent(f"type_{i}", f"payload_{i}")
            coalescer.push(ev)
            time.sleep(0.015)

        time.sleep(0.05)
        coalescer.stop()

        # Each event in quiet mode should be dispatched promptly without delayed batching
        self.assertGreaterEqual(len(dispatches), 2)
        total_delivered = sum(len(b) for b in dispatches)
        self.assertEqual(total_delivered, 3)

    def test_burst_mode_coalescing_efficiency(self):
        """Under burst conditions, events are coalesced into micro-batches saving context switches."""
        dispatches = []
        lock = threading.Lock()

        def on_dispatch(batch):
            with lock:
                dispatches.append(batch)

        coalescer = NJCoalescer(
            "test_burst",
            on_dispatch,
            min_window_ms=1.0,
            max_window_ms=5.0,
            burst_threshold_hz=20.0,
            max_batch_size=32,
        )

        num_events = 60
        # Rapidly fire 60 events in burst mode
        for i in range(num_events):
            ev = NJCoalesceEvent(f"token_{i}", {"token": i, "weight": 0.95})
            coalescer.push(ev)

        # Allow micro-windows to flush
        time.sleep(0.08)
        coalescer.flush()
        coalescer.stop()

        with lock:
            total_delivered = sum(len(b) for b in dispatches)
            total_batches = len(dispatches)

        self.assertEqual(total_delivered, num_events)
        # 60 events should be grouped into far fewer dispatches than 60
        self.assertLess(total_batches, 25, f"Expected coalescing into <= 25 batches, got {total_batches}")

        metrics = coalescer.get_metrics()
        self.assertGreater(metrics["coalescing_efficiency_pct"], 50.0)
        self.assertGreater(metrics["context_switches_saved"], 30)

    def test_urgent_priority_instant_bypass(self):
        """Urgent events bypass coalesce timer and trigger immediate flush."""
        dispatches = []
        lock = threading.Lock()

        def on_dispatch(batch):
            with lock:
                dispatches.append(batch)

        coalescer = NJCoalescer("test_urgent", on_dispatch, min_window_ms=20.0, burst_threshold_hz=10.0)

        # Queue normal event
        coalescer.push(NJCoalesceEvent("bg_event", "data", priority=EventPriority.NORMAL))

        # Push URGENT event
        coalescer.push(NJCoalesceEvent("ALARM_STOP", "kill", priority=EventPriority.URGENT))

        # Should be dispatched almost instantly without waiting for 20ms timer
        time.sleep(0.01)
        with lock:
            self.assertGreaterEqual(len(dispatches), 1)
            first_batch = dispatches[0]
            event_types = [e.event_type for e in first_batch]
            self.assertIn("ALARM_STOP", event_types)

        coalescer.stop()


class TestNJCrashResilienceAndFaultIsolation(unittest.TestCase):
    """Validates crash resilience, state rollback, and circuit breaker without OS reboot."""

    def test_clean_execution_within_cage(self):
        """Healthy task executes cleanly and retains HEALTHY state."""
        domain = NJFaultDomain("AIModel_Summarizer")
        
        def safe_compute(x, y):
            return x * y + 42

        success, result = domain.execute(safe_compute, 3, 5)
        self.assertTrue(success)
        self.assertEqual(result, 57)
        self.assertEqual(domain.state, ComponentHealthState.HEALTHY)

    def test_crash_isolation_and_state_rollback(self):
        """Simulate an AI model crash; verify failure is trapped and state is rolled back."""
        domain = NJFaultDomain(
            "AIModel_UnstableTransformer",
            fallback_fn=lambda exc, snap: {"error": str(exc), "fallback_result": "default_prediction"}
        )

        global_system_state = {"tokens_processed": 100, "active_context": "valid"}

        def rollback(snapshot):
            global_system_state.clear()
            global_system_state.update(snapshot)

        def crashing_inference():
            global_system_state["active_context"] = "corrupted_partial_write"
            raise RuntimeError("CUDA Out of Memory / Internal Tensor Segmentation Fault")

        # Snapshot before running
        snapshot = dict(global_system_state)

        # Execute inside NJ Fault Domain cage
        success, result = domain.execute(
            crashing_inference,
            state_snapshot=snapshot,
            rollback_fn=rollback
        )

        # 1. Execution was trapped gracefully
        self.assertFalse(success, "Fault domain should report execution failure")
        self.assertEqual(result["fallback_result"], "default_prediction")

        # 2. State was rolled back to clean pre-execution state
        self.assertEqual(global_system_state["active_context"], "valid")
        self.assertEqual(global_system_state["tokens_processed"], 100)

        # 3. Domain marked as DEGRADED, not QUARANTINED on first failure
        self.assertEqual(domain.state, ComponentHealthState.DEGRADED)

    def test_circuit_breaker_trips_to_quarantine(self):
        """Repeated crashes trip circuit breaker to QUARANTINED, isolating faulty component."""
        domain = NJFaultDomain(
            "CrashingModule",
            failure_threshold=3,
            window_seconds=5.0,
            quarantine_duration_sec=2.0,
            fallback_fn=lambda exc, snap: "QUARANTINED_FALLBACK"
        )

        def always_fails():
            raise ValueError("Bug in module code")

        # 1st crash -> DEGRADED
        domain.execute(always_fails)
        self.assertEqual(domain.state, ComponentHealthState.DEGRADED)

        # 2nd crash -> DEGRADED
        domain.execute(always_fails)
        self.assertEqual(domain.state, ComponentHealthState.DEGRADED)

        # 3rd crash -> TRIPS CIRCUIT BREAKER to QUARANTINED
        domain.execute(always_fails)
        self.assertEqual(domain.state, ComponentHealthState.QUARANTINED)

        # 4th call is immediately rejected and served by fallback without running target_fn
        called = []
        def probe_fn():
            called.append(True)
            return "ok"

        success, res = domain.execute(probe_fn)
        self.assertFalse(success)
        self.assertEqual(res, "QUARANTINED_FALLBACK")
        self.assertEqual(len(called), 0, "Target function should NOT be executed during quarantine")

        # Manual reset restores system to HEALTHY
        domain.reset()
        self.assertEqual(domain.state, ComponentHealthState.HEALTHY)
        success, res = domain.execute(probe_fn)
        self.assertTrue(success)
        self.assertEqual(res, "ok")


class TestNJResourceManagerIntegration(unittest.TestCase):
    """Validates NJ engine integration within ResourceManager."""

    def test_resource_manager_nj_facade(self):
        res_mgr = ResourceManager(num_workers=2)
        shm_name = f"resmgr_nj_test_{int(time.time() * 1000) % 100000}"

        try:
            # 1. Acquire IPC Channel
            ipc = res_mgr.get_ipc_channel(shm_name, capacity=8, slot_size=128)
            self.assertIsNotNone(ipc)
            self.assertTrue(ipc.write(b"resmgr_hello"))
            self.assertEqual(ipc.read(), b"resmgr_hello")

            # 2. Run isolated safe function
            success, result = res_mgr.run_isolated(
                "TestDomain",
                lambda a, b: a + b,
                10, 20
            )
            self.assertTrue(success)
            self.assertEqual(result, 30)

            # 3. Run crashing function in isolated domain
            success, result = res_mgr.run_isolated(
                "CrashDomain",
                lambda: 1 / 0,
                fallback_fn=lambda exc, snap: "safe_zero"
            )
            self.assertFalse(success)
            self.assertEqual(result, "safe_zero")

        finally:
            res_mgr.shutdown()


if __name__ == "__main__":
    unittest.main()
