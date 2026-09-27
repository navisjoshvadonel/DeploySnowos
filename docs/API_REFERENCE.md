# SnowOS Kernel API Reference

This document provides a technical reference for all public interfaces across the SnowOS Kernel.

---

## 1. Kernel Performance Subsystem (`kernel_layer.performance`)

### 1.1 `MLFQScheduler`
Multi-Level Feedback Queue Scheduler with 4 priority queues and an automatic anti-starvation boost.

```python
from kernel_layer.performance import MLFQScheduler, QueueLevel

scheduler = MLFQScheduler(num_workers=4, boost_interval_sec=3.0)
scheduler.start()

# Submit a task
task = scheduler.submit(
    name="ai_inference",
    func=my_inference_func,
    arg1, arg2,
    priority=QueueLevel.Q1_INTERACTIVE
)

# Shutdown
scheduler.stop()
```

#### Queue Levels
- `QueueLevel.Q0_REALTIME`: Real-time system input, telemetry, and security alarms.
- `QueueLevel.Q1_INTERACTIVE`: User-facing shell and UI intelligence updates.
- `QueueLevel.Q2_STANDARD`: General AI reasoning and background tasks.
- `QueueLevel.Q3_BATCH`: Heavy background learning, checkpointing, and compaction.

---

### 1.2 `VirtualMemoryManager` & `AIMemoryGovernor`
Simulates demand-paged virtual memory with 4KB page frames, LRU page eviction to swap, and quota enforcement.

```python
from kernel_layer.performance import VirtualMemoryManager, AIMemoryGovernor

# Virtual Memory Manager
vmm = VirtualMemoryManager(total_physical_pages=64, page_size=4096)
page = vmm.allocate_page(process_id=101, is_writable=True, is_user=True)
vmm.write_virtual(process_id=101, page_num=page.page_number, offset=0, data=b"data")
data = vmm.read_virtual(process_id=101, page_num=page.page_number, offset=0, length=4)

# AI Memory Governor
governor = AIMemoryGovernor(soft_limit_mb=512.0, hard_limit_mb=1024.0)
pressure, current_mb = governor.enforce_quota()
```

---

### 1.3 Synchronization Primitives (`sync_primitives.py`)
Deadlock-detecting and fair concurrency primitives.

- `DeadlockDetectingMutex(name)`: Mutex with circular wait detection graph; raises `DeadlockDetectedException` instead of locking the thread permanently.
- `AdaptiveSpinlock(max_spins=1000)`: Hybrid spin-then-sleep lock for sub-microsecond synchronization.
- `FairCountingSemaphore(initial_value, max_value)`: FIFO queue-ordered semaphore preventing thread starvation.
- `FairRWLock()`: Phase-fair reader-writer lock preventing writer starvation.

---

## 2. The NJ Engine (`kernel_layer.performance.nj_engine`)

### 2.1 `NJRingBuffer`
Zero-copy POSIX shared-memory ring buffer allocated in `/dev/shm`.

```python
from kernel_layer.performance import NJRingBuffer

# Server / Writer
server_rb = NJRingBuffer(name="snowos_stream", capacity=128, slot_size=4096, create=True)
server_rb.write(b"RAW_TENSOR_BYTES", channel_id=0, timeout_ms=50.0)

# Client / Reader
client_rb = NJRingBuffer(name="snowos_stream", create=False)
payload = client_rb.read(channel_id=0, timeout_ms=50.0)

# Clean Teardown
server_rb.unlink()
```

---

### 2.2 `NJCoalescer`
Adaptive micro-burst event coalescer that throttles high-frequency interrupt/event storms.

```python
from kernel_layer.performance import NJCoalescer, NJCoalesceEvent, EventPriority

def handle_batch(batch: list[NJCoalesceEvent]):
    for event in batch:
        process(event.payload)

coalescer = NJCoalescer(
    name="token_stream",
    dispatch_callback=handle_batch,
    min_window_ms=0.2,
    max_window_ms=4.0,
    burst_threshold_hz=50.0
)

# Push normal event (coalesced during bursts)
coalescer.push(NJCoalesceEvent("token", {"id": 42}, priority=EventPriority.NORMAL))

# Push urgent event (immediately triggers zero-delay flush)
coalescer.push(NJCoalesceEvent("HALT", "alarm", priority=EventPriority.URGENT))
```

---

### 2.3 `NJFaultDomain`
Sandboxed execution cage with state snapshotting, rollback, and circuit breaker.

```python
from kernel_layer.performance import NJFaultDomain

domain = NJFaultDomain(
    name="AIWorker",
    failure_threshold=3,
    window_seconds=10.0,
    quarantine_duration_sec=15.0,
    fallback_fn=lambda exc, snap: {"status": "fallback", "error": str(exc)}
)

success, result = domain.execute(
    target_fn=untrusted_ai_code,
    state_snapshot={"active_user": "snowjd"},
    rollback_fn=lambda snap: restore_state(snap)
)
```

---

## 3. Hardware Interfacing & Storage (`kernel_layer.io_hardware`)

### 3.1 `DriverManager` & `DeviceDriver`
Modular driver lifecycle with dependency enforcement and NJ cage isolation.

```python
from kernel_layer.io_hardware import DriverManager, DeviceInfo, DriverType, VirtualRamDiskDriver

mgr = DriverManager()
dev = DeviceInfo("disk0", vendor_id=0x1A00, product_id=0x0001, device_class=DriverType.BLOCK, bus_address="virt://disk0")
driver = mgr.register_device(dev)

# Safe I/O execution
success, res = mgr.safe_io("VirtualRamDiskDriver", lambda drv: drv.read(offset=0, size=512))
```

---

### 3.2 `HardwareAccelerator`
Unified multi-backend compute engine (TPU Systolic, GPU Compute, CPU SIMD).

```python
from kernel_layer.io_hardware import HardwareAccelerator, AccelerationTier

accel = HardwareAccelerator(preferred_tier=AccelerationTier.TPU_SYSTOLIC)

# Matrix Multiplication (GEMM)
A = [[1.0, 2.0], [3.0, 4.0]]
B = [[5.0, 6.0], [7.0, 8.0]]
C, stats = accel.matmul(A, B)

# Transformer Activations
gelu_out = accel.activation_gelu([0.0, 1.0, -1.0])
softmax_out = accel.softmax([1.0, 2.0, 3.0])
```

---

### 3.3 `SnowFS` & `BlockDevice`
ext2/FAT-inspired structured block filesystem with CRC32 integrity verification.

```python
from kernel_layer.io_hardware import SnowFS, BlockDevice

bdev = BlockDevice(total_blocks=1024, block_size=1024)
fs = SnowFS.format(bdev, total_inodes=128)

# Directory & File I/O
fs.mkdir("/etc")
fs.write_file("/etc/config.json", b'{"key": "value"}')
data = fs.read_file("/etc/config.json")  # Raises DataIntegrityError on CRC mismatch

# Filesystem Audit
is_clean, issues = fs.fsck()
```

---

## 4. Kernel Boot Sequence (`kernel_layer.boot_init`)

```python
from kernel_layer.boot_init import KernelBootSequence

bootloader = KernelBootSequence(storage_blocks=1024, scheduler_workers=4)
ctx = bootloader.boot()

assert ctx.is_operational()
print(f"Boot finished in {ctx.boot_time_ms} ms")

# Clean teardown
bootloader.shutdown()
```
