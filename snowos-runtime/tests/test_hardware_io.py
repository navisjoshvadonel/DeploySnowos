#!/usr/bin/env python3
"""
SnowOS Kernel — Hardware Interfacing, Drivers & I/O Test Suite.
=============================================================

Validates:
  1. Device Driver Framework:
     - Driver lifecycle (probe, init, start, stop, unload).
     - Device hotplug and automated driver binding.
     - Dependency tracking and safe unloading.
     - VirtualRamDiskDriver block read/write and ioctl commands.
     - Fault isolation: driver exceptions do not crash DriverManager.

  2. Hardware Acceleration:
     - TPU Systolic Array GEMM accuracy and GFLOPS tracking.
     - GPU Compute Layer tiled matrix multiplication.
     - CPU SIMD cache-blocked matrix kernels & GeLU activation.
     - Unified HardwareAccelerator multi-tier fallback arbitration.

  3. SnowFS Structured Block Filesystem:
     - Formatting and mounting with superblock CRC32 verification.
     - Hierarchical directories and file creation.
     - File read/write throughput and multi-block allocation.
     - Data integrity checks: bit flip tampering caught by CRC32 check.
     - Complete fsck sanity verification.
"""

import sys
import os
import time
import unittest

# Ensure snowos-runtime/src is in PYTHONPATH
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from kernel_layer.io_hardware import (
    DeviceDriver,
    DriverManager,
    DeviceInfo,
    DriverType,
    DriverState,
    VirtualRamDiskDriver,
    GPUDriver,
    TPUSystolicDriver,
    HardwareAccelerator,
    TPUSystolicAccelerator,
    GPUComputeAccelerator,
    CPUSimdAccelerator,
    AccelerationTier,
    SnowFS,
    BlockDevice,
    FileType,
    DataIntegrityError,
    FilesystemError,
)


class TestDeviceDriverFramework(unittest.TestCase):
    """Validates driver lifecycle, binding, and crash isolation."""

    def setUp(self):
        self.mgr = DriverManager()

    def test_ramdisk_driver_lifecycle_and_io(self):
        """Verify VirtualRamDiskDriver probes, initializes, and performs block I/O."""
        dev_info = DeviceInfo(
            device_id="ramdisk0",
            vendor_id=0x1A00,
            product_id=0x0001,
            device_class=DriverType.BLOCK,
            bus_address="virtual://ramdisk0",
            resources={"total_sectors": 512, "sector_size": 512},
        )

        driver = self.mgr.register_device(dev_info)
        self.assertIsNotNone(driver)
        self.assertIsInstance(driver, VirtualRamDiskDriver)
        self.assertEqual(driver.state, DriverState.RUNNING)

        # Write data to RAM disk
        test_payload = b"SnowOS_Kernel_Driver_Payload_Block_Data"
        bytes_written = driver.write(offset=0, data=test_payload)
        self.assertEqual(bytes_written, len(test_payload))

        # Read back data
        read_back = driver.read(offset=0, size=len(test_payload))
        self.assertEqual(read_back, test_payload)

        # Ioctl verification
        sec_sz = driver.ioctl(cmd=0x01)
        self.assertEqual(sec_sz, 512)

        # Unload driver
        self.assertTrue(self.mgr.unload_driver(driver.name))
        self.assertEqual(driver.state, DriverState.UNLOADED)

    def test_driver_dependency_enforcement(self):
        """Verify that a driver cannot be unloaded if another loaded driver depends on it."""
        class MockBusDriver(DeviceDriver):
            name = "MockBusDriver"
            driver_type = DriverType.BUS

        class MockChildDriver(DeviceDriver):
            name = "MockChildDriver"
            dependencies = ["MockBusDriver"]

        self.mgr.register_driver(MockBusDriver)
        self.mgr.register_driver(MockChildDriver)

        # Loading child automatically loads prerequisite bus driver
        child = self.mgr.load_driver("MockChildDriver")
        self.assertIsNotNone(child)
        self.assertIsNotNone(self.mgr.get_driver("MockBusDriver"))

        # Attempting to unload bus driver without force fails
        unloaded = self.mgr.unload_driver("MockBusDriver", force=False)
        self.assertFalse(unloaded, "Bus driver should not unload while dependent child is active")

        # Unloading child first allows bus driver to unload cleanly
        self.assertTrue(self.mgr.unload_driver("MockChildDriver"))
        self.assertTrue(self.mgr.unload_driver("MockBusDriver"))

    def test_faulty_driver_crash_isolation(self):
        """Verify driver exception in I/O is safely trapped by NJ Fault Cage."""
        class CrashingDriver(DeviceDriver):
            name = "CrashingDriver"
            def read(self, offset: int, size: int) -> bytes:
                raise RuntimeError("Hardware Bus Parity Error in Read")

        self.mgr.register_driver(CrashingDriver)
        self.mgr.load_driver("CrashingDriver")

        # safe_io traps the crash without raising an unhandled exception
        success, result = self.mgr.safe_io("CrashingDriver", lambda drv: drv.read(0, 10))
        self.assertFalse(success)
        self.assertIsInstance(result, RuntimeError)


class TestHardwareAcceleration(unittest.TestCase):
    """Validates TPU, GPU, and CPU SIMD acceleration tiers."""

    def test_tpu_systolic_gemm_accuracy(self):
        """Verify TPU systolic matrix multiplication matches mathematical dot product."""
        tpu = TPUSystolicAccelerator(array_size=64)

        # A: (2x3), B: (3x2)
        A = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        B = [[7.0, 8.0], [9.0, 1.0], [2.0, 3.0]]
        # Expected C:
        # C[0][0] = 1*7 + 2*9 + 3*2 = 7 + 18 + 6 = 31
        # C[0][1] = 1*8 + 2*1 + 3*3 = 8 + 2 + 9 = 19
        # C[1][0] = 4*7 + 5*9 + 6*2 = 28 + 45 + 12 = 85
        # C[1][1] = 4*8 + 5*1 + 6*3 = 32 + 5 + 18 = 55
        expected = [[31.0, 19.0], [85.0, 55.0]]

        C, stats = tpu.gemm(A, B)
        self.assertEqual(C, expected)
        self.assertEqual(stats["tier"], "TPU_SYSTOLIC")
        self.assertGreater(stats["gflops"], 0.0)

    def test_gpu_compute_tiled_gemm(self):
        """Verify GPU compute layer tiled matrix multiplication."""
        gpu = GPUComputeAccelerator(vram_mb=4096)
        A = [[2.0, 0.0], [1.0, 3.0]]
        B = [[1.0, 2.0], [3.0, 4.0]]
        # C[0][0] = 2, C[0][1] = 4
        # C[1][0] = 10, C[1][1] = 14
        expected = [[2.0, 4.0], [10.0, 14.0]]

        C, stats = gpu.gemm(A, B, tile_size=2)
        self.assertEqual(C, expected)
        self.assertEqual(stats["tier"], "GPU_COMPUTE")

    def test_cpu_simd_cache_blocked_gemm_and_gelu(self):
        """Verify CPU SIMD vector operations and GeLU activation."""
        simd = CPUSimdAccelerator()
        A = [[1.0, 2.0], [3.0, 4.0]]
        B = [[5.0, 6.0], [7.0, 8.0]]
        expected = [[19.0, 22.0], [43.0, 50.0]]

        C, stats = simd.gemm(A, B)
        self.assertEqual(C, expected)
        self.assertEqual(stats["tier"], "CPU_SIMD")

        # Test GELU activation: GeLU(0.0) should be 0.0
        gelu_out = simd.activation_gelu([0.0, 1.0, -1.0])
        self.assertAlmostEqual(gelu_out[0], 0.0, places=4)
        self.assertGreater(gelu_out[1], 0.8)  # GeLU(1.0) approx 0.8413

    def test_unified_accelerator_fallback(self):
        """Verify unified HardwareAccelerator arbitrates compute across tiers."""
        accel = HardwareAccelerator(preferred_tier=AccelerationTier.TPU_SYSTOLIC)
        A = [[1.0, 2.0], [3.0, 4.0]]
        B = [[1.0, 0.0], [0.0, 1.0]]

        C, stats = accel.matmul(A, B)
        self.assertEqual(C, A)  # Identity multiply
        self.assertEqual(stats["tier"], "TPU_SYSTOLIC")

        topo = accel.get_hardware_topology()
        self.assertIn("active_preferred_tier", topo)
        self.assertIn("cpu_simd_instruction_set", topo)


class TestSnowFSStructuredFilesystem(unittest.TestCase):
    """Validates SnowFS block filesystem formatting, I/O, and CRC32 integrity."""

    def setUp(self):
        # 512 blocks of 1024 bytes = 512KB virtual block device
        self.bdev = BlockDevice(total_blocks=512, block_size=1024)
        self.fs = SnowFS.format(self.bdev, total_inodes=64)

    def test_format_and_mount_state(self):
        """Verify clean format and superblock metadata."""
        self.assertTrue(self.fs.is_mounted)
        self.assertEqual(self.fs.total_blocks, 512)
        self.assertGreater(self.fs.free_blocks, 450)
        self.assertEqual(self.fs.total_inodes, 64)

        # Directory listing of root should contain '.' and '..'
        root_entries = self.fs.list_dir("/")
        names = [e["name"] for e in root_entries]
        self.assertIn(".", names)
        self.assertIn("..", names)

    def test_hierarchical_directory_and_file_creation(self):
        """Verify creating directories and nested files."""
        # 1. Create /etc and /var/log directories
        self.fs.mkdir("/etc")
        self.fs.mkdir("/var")
        self.fs.mkdir("/var/log")

        # Verify /var contains 'log'
        var_entries = self.fs.list_dir("/var")
        var_names = [e["name"] for e in var_entries]
        self.assertIn("log", var_names)

        # 2. Write file into /etc/snowos.conf
        config_data = b'{"os": "SnowOS", "version": "2.0.0", "ai_core": "Nyx"}'
        bytes_written = self.fs.write_file("/etc/snowos.conf", config_data)
        self.assertEqual(bytes_written, len(config_data))

        # 3. Read back file and verify exact content
        read_data = self.fs.read_file("/etc/snowos.conf")
        self.assertEqual(read_data, config_data)

    def test_multi_block_file_io(self):
        """Verify file spanning multiple 1024-byte data blocks reads/writes cleanly."""
        # Create 3500 bytes payload (> 3 blocks)
        large_payload = b"SNOW_OS_DATA_CHUNK_" * 175  # 19 * 175 = 3325 bytes
        self.fs.write_file("/var/log/kernel.log", large_payload)

        read_payload = self.fs.read_file("/var/log/kernel.log")
        self.assertEqual(read_payload, large_payload)

    def test_data_integrity_check_detects_corruption(self):
        """Verify CRC32 integrity check detects bit flips and raises DataIntegrityError."""
        original_data = b"Critical_Kernel_Parameters_Secure_Config"
        self.fs.write_file("/etc/secure.dat", original_data)

        # Ensure it reads correctly first
        self.assertEqual(self.fs.read_file("/etc/secure.dat"), original_data)

        # Tamper with the raw block device underlying this file!
        _, inode, _ = self.fs._traverse_path("/etc/secure.dat")
        self.assertIsNotNone(inode)
        data_block = inode.direct_blocks[0]

        # Read the raw block, flip a bit, and write it back
        raw_block = bytearray(self.bdev.read_block(data_block))
        raw_block[0] ^= 0xFF  # Flip byte
        self.bdev.write_block(data_block, bytes(raw_block))

        # Reading the file must now fail with DataIntegrityError
        with self.assertRaises(DataIntegrityError):
            self.fs.read_file("/etc/secure.dat")

    def test_fsck_filesystem_consistency(self):
        """Verify fsck validates healthy filesystem."""
        self.fs.mkdir("/system")
        self.fs.write_file("/system/init.cfg", b"INIT_STAGE=2")

        is_clean, issues = self.fs.fsck()
        self.assertTrue(is_clean, f"fsck reported issues on clean disk: {issues}")
        self.assertEqual(len(issues), 0)


if __name__ == "__main__":
    unittest.main()
