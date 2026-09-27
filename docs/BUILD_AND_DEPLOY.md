# SnowOS Build, Testing & Deployment Guide

This guide covers building, testing, deploying, and verifying SnowOS in production environments.

---

## 1. System Requirements

- **Operating System**: Linux kernel 5.15 or newer (Ubuntu 22.04+, Debian 12+, Fedora 38+).
- **Python**: Version 3.10 or newer (tested on Python 3.12).
- **RAM**: Minimum 2 GB (4 GB recommended for AI reasoning).
- **Storage**: Minimum 10 GB free space.
- **Shared Memory**: POSIX `/dev/shm` mounted with read/write permissions.
- **Optional Hardware**:
  - NVIDIA GPU with CUDA drivers (for `GPUComputeAccelerator`).
  - Google Coral / TPU device (for `TPUSystolicAccelerator`).
  - Host CPU with AVX2 or AVX-512 extensions (automatically detected).

---

## 2. Environment Setup

```bash
# Clone the repository
git clone https://github.com/navisjoshvadonel/DeploySnowos.git
cd DeploySnowos

# Ensure python dependencies are installed
pip install -r snowos-runtime/requirements.txt # or install psutil
```

---

## 3. Automated Testing Suite

SnowOS enforces strict test-driven development across all kernel layers.

### Run All Unit & Stress Tests
```bash
python3 -m unittest discover -s snowos-runtime/tests
```

### Run Kernel Resource Management Tests
```bash
python3 -m unittest snowos-runtime/tests/test_kernel_resource_management.py
```
*Validates MLFQ priority preemption, anti-starvation boost, virtual memory demand paging, LRU swap eviction, and deadlock-detecting mutexes.*

### Run NJ Engine Performance & Fault Resilience Tests
```bash
python3 -m unittest snowos-runtime/tests/test_nj_performance.py
```
*Validates zero-copy POSIX shared memory ring buffers, micro-burst event coalescing, and fault domain rollback cages.*

### Run Hardware Interfacing, Acceleration & SnowFS Tests
```bash
python3 -m unittest snowos-runtime/tests/test_hardware_io.py
```
*Validates device driver lifecycles, TPU systolic GEMM math, GPU compute workgroups, CPU SIMD vectorization, and SnowFS CRC32 corruption detection.*

### Run High-Load Stress Tests
```bash
python3 -m unittest snowos-runtime/tests/test_kernel_stress.py
```
*Validates 1,000 concurrent MLFQ tasks, 2,000 shared memory packets under backpressure, multi-block filesystem stress, and chaos crash storms.*

---

## 4. Production Deployment & Systemd Services

SnowOS provides systemd unit files hardened with defense-in-depth sandboxing.

### Available Systemd Services
1. `snowos-boot.service`: Executes `boot_orchestrator.py` at boot.
2. `snowos-broker.service`: Runs the Permission Broker daemon with `SO_PEERCRED` validation.
3. `snowos-sentinel.service`: Runs the AI Sentinel behavioral anomaly daemon.
4. `snowos-nyx.service`: Runs the Nyx cognitive assistant service.

### Deploying Services
```bash
# Copy systemd unit files
sudo cp snowos-runtime/services/*.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable --now snowos-boot.service
sudo systemctl enable --now snowos-broker.service
sudo systemctl enable --now snowos-sentinel.service
```

### Validating System Status
```bash
# Check runtime health
cat /run/snowos/boot-status.json

# Check audit log
cat /var/log/snowos/boot-history.jsonl
```
