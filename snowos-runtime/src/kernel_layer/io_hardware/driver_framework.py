"""
SnowOS Kernel — Device Driver Framework
=======================================

Provides a clean, modular, and fault-isolated architecture for loading,
unloading, configuring, and monitoring device drivers in SnowOS.

Key Features:
  - Standardized Driver Lifecycle (probe, init, start, stop, unload, ioctl).
  - Topological Dependency Resolution (e.g. Bus -> Controller -> Device).
  - Dynamic Hotplug & Device Registry with automatic driver matching.
  - Crash Isolation via NJ Fault Domains (faulty driver crashes do not freeze OS).
  - Concrete drivers for Block Storage (RAM Disk), GPU, and TPU acceleration.
"""

from __future__ import annotations

import os
import time
import logging
import threading
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

from kernel_layer.performance.nj_engine import NJFaultDomain, ComponentHealthState

logger = logging.getLogger("SnowOS.DriverFramework")


class DriverType(Enum):
    BUS = auto()
    BLOCK = auto()
    CHAR = auto()
    NET = auto()
    ACCEL_GPU = auto()
    ACCEL_TPU = auto()
    STORAGE = auto()
    INPUT = auto()


class DriverState(Enum):
    UNLOADED = auto()
    PROBING = auto()
    INITIALIZED = auto()
    RUNNING = auto()
    SUSPENDED = auto()
    FAULTED = auto()


class DeviceInfo:
    """Hardware device descriptor identified on a bus."""

    def __init__(
        self,
        device_id: str,
        vendor_id: int,
        product_id: int,
        device_class: DriverType,
        bus_address: str,
        resources: Optional[Dict[str, Any]] = None,
    ):
        self.device_id = device_id
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device_class = device_class
        self.bus_address = bus_address
        self.resources = resources or {}
        self.bound_driver: Optional[str] = None

    def __repr__(self) -> str:
        return (
            f"<DeviceInfo {self.device_id} ({self.device_class.name}) "
            f"VID:0x{self.vendor_id:04x} PID:0x{self.product_id:04x} @ {self.bus_address}>"
        )


class DeviceDriver:
    """
    Abstract Base Class for all SnowOS Device Drivers.
    Enforces a strict lifecycle and standard I/O entry points.
    """

    name: str = "GenericDriver"
    version: str = "1.0.0"
    driver_type: DriverType = DriverType.CHAR
    supported_devices: List[Tuple[int, int]] = []  # List of (vendor_id, product_id)
    dependencies: List[str] = []                   # Driver names required before loading

    def __init__(self):
        self.state: DriverState = DriverState.UNLOADED
        self.device: Optional[DeviceInfo] = None
        self._lock = threading.Lock()
        self.stats: Dict[str, Any] = {
            "bytes_read": 0,
            "bytes_written": 0,
            "ioctls_handled": 0,
            "errors": 0,
        }

    def probe(self, device: DeviceInfo) -> bool:
        """Inspect device to verify compatibility and hardware presence."""
        if not self.supported_devices:
            return device.device_class == self.driver_type
        for vid, pid in self.supported_devices:
            if device.vendor_id == vid and (pid == 0xFFFF or device.product_id == pid):
                return True
        return False

    def init(self, device: DeviceInfo) -> bool:
        """Allocate private data, allocate registers, map MMIO."""
        self.device = device
        self.state = DriverState.INITIALIZED
        return True

    def start(self) -> bool:
        """Enable interrupts and transition to RUNNING state."""
        self.state = DriverState.RUNNING
        return True

    def stop(self) -> bool:
        """Disable interrupts and halt active DMA/transfers."""
        self.state = DriverState.SUSPENDED
        return True

    def unload(self) -> bool:
        """Release MMIO, unmap IRQ, free driver resources."""
        self.state = DriverState.UNLOADED
        self.device = None
        return True

    def read(self, offset: int, size: int) -> bytes:
        """Read data from device."""
        return b""

    def write(self, offset: int, data: bytes) -> int:
        """Write data to device."""
        return 0

    def ioctl(self, cmd: int, arg: Any = None) -> Any:
        """Dispatch device-specific control command."""
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Concrete Core Drivers
# ─────────────────────────────────────────────────────────────────────────────

class VirtualRamDiskDriver(DeviceDriver):
    """Block driver providing high-speed in-memory raw block storage."""

    name = "VirtualRamDiskDriver"
    version = "1.2.0"
    driver_type = DriverType.BLOCK
    supported_devices = [(0x1A00, 0x0001)]  # SnowOS Vendor, RAMDisk PID

    def __init__(self, sector_size: int = 512, total_sectors: int = 2048):
        super().__init__()
        self.sector_size = sector_size
        self.total_sectors = total_sectors
        self.total_bytes = sector_size * total_sectors
        self._storage: Optional[bytearray] = None

    def init(self, device: DeviceInfo) -> bool:
        super().init(device)
        sectors = device.resources.get("total_sectors", self.total_sectors)
        sec_sz = device.resources.get("sector_size", self.sector_size)
        self.sector_size = sec_sz
        self.total_sectors = sectors
        self.total_bytes = sec_sz * sectors
        self._storage = bytearray(self.total_bytes)
        return True

    def read(self, offset: int, size: int) -> bytes:
        if self.state != DriverState.RUNNING or self._storage is None:
            raise IOError("RAMDisk driver is not in RUNNING state")
        if offset < 0 or offset + size > self.total_bytes:
            raise IOError(f"Read out of bounds: offset {offset} + size {size} > {self.total_bytes}")
        with self._lock:
            data = bytes(self._storage[offset : offset + size])
            self.stats["bytes_read"] += len(data)
            return data

    def write(self, offset: int, data: bytes) -> int:
        if self.state != DriverState.RUNNING or self._storage is None:
            raise IOError("RAMDisk driver is not in RUNNING state")
        size = len(data)
        if offset < 0 or offset + size > self.total_bytes:
            raise IOError(f"Write out of bounds: offset {offset} + size {size} > {self.total_bytes}")
        with self._lock:
            self._storage[offset : offset + size] = data
            self.stats["bytes_written"] += size
            return size

    def ioctl(self, cmd: int, arg: Any = None) -> Any:
        self.stats["ioctls_handled"] += 1
        if cmd == 0x01:  # GET_SECTOR_SIZE
            return self.sector_size
        elif cmd == 0x02:  # GET_SECTOR_COUNT
            return self.total_sectors
        elif cmd == 0x03:  # FLUSH
            return True
        return None

    def unload(self) -> bool:
        self._storage = None
        return super().unload()


class GPUDriver(DeviceDriver):
    """Hardware acceleration driver for GPU compute units."""

    name = "GPUDriver"
    version = "2.0.0"
    driver_type = DriverType.ACCEL_GPU
    supported_devices = [(0x10DE, 0xFFFF), (0x8086, 0x4E00)]  # NVIDIA, Intel GPU

    def __init__(self):
        super().__init__()
        self.vram_total_mb = 8192
        self.vram_used_mb = 0
        self.compute_cores = 2560
        self.clock_mhz = 1750

    def init(self, device: DeviceInfo) -> bool:
        super().init(device)
        self.vram_total_mb = device.resources.get("vram_mb", 8192)
        self.compute_cores = device.resources.get("cores", 2560)
        return True

    def ioctl(self, cmd: int, arg: Any = None) -> Any:
        self.stats["ioctls_handled"] += 1
        if cmd == 0x10:  # ALLOC_VRAM
            alloc_mb = int(arg) if arg else 0
            if self.vram_used_mb + alloc_mb <= self.vram_total_mb:
                self.vram_used_mb += alloc_mb
                return True
            return False
        elif cmd == 0x11:  # FREE_VRAM
            free_mb = int(arg) if arg else 0
            self.vram_used_mb = max(0, self.vram_used_mb - free_mb)
            return True
        elif cmd == 0x12:  # GET_GPU_STATUS
            return {
                "vram_total_mb": self.vram_total_mb,
                "vram_used_mb": self.vram_used_mb,
                "compute_cores": self.compute_cores,
                "clock_mhz": self.clock_mhz,
            }
        return None


class TPUSystolicDriver(DeviceDriver):
    """Hardware acceleration driver for TPU / NPU matrix systolic engines."""

    name = "TPUSystolicDriver"
    version = "1.5.0"
    driver_type = DriverType.ACCEL_TPU
    supported_devices = [(0x1DA0, 0x0020)]  # SnowOS TPU Controller

    def __init__(self):
        super().__init__()
        self.matrix_dim = 64  # 64x64 systolic array
        self.precision_modes = ["bfloat16", "float16", "int8", "float32"]
        self.active_precision = "bfloat16"

    def ioctl(self, cmd: int, arg: Any = None) -> Any:
        self.stats["ioctls_handled"] += 1
        if cmd == 0x20:  # SET_PRECISION
            if arg in self.precision_modes:
                self.active_precision = arg
                return True
            return False
        elif cmd == 0x21:  # GET_SYSTOLIC_INFO
            return {
                "matrix_dim": self.matrix_dim,
                "active_precision": self.active_precision,
                "ops_per_cycle": self.matrix_dim * self.matrix_dim * 2,
            }
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Device Driver Manager (Lifecycle, Hotplug, and Fault Isolation)
# ─────────────────────────────────────────────────────────────────────────────

class DriverManager:
    """
    Central Kernel Subsystem for managing device drivers:
      - Clean loading/unloading with dependency tracking.
      - Dynamic device registration and hotplug binding.
      - Sandboxed execution via NJ Fault Domains.
    """

    def __init__(self):
        self._driver_classes: Dict[str, Type[DeviceDriver]] = {}
        self._loaded_drivers: Dict[str, DeviceDriver] = {}
        self._devices: Dict[str, DeviceInfo] = {}
        self._driver_cages: Dict[str, NJFaultDomain] = {}
        self._lock = threading.Lock()

        # Register default kernel drivers
        self.register_driver(VirtualRamDiskDriver)
        self.register_driver(GPUDriver)
        self.register_driver(TPUSystolicDriver)

    def register_driver(self, driver_cls: Type[DeviceDriver]):
        """Register a driver class in the kernel driver repository."""
        with self._lock:
            self._driver_classes[driver_cls.name] = driver_cls
            logger.info("DriverManager: Registered driver '%s' (v%s)", driver_cls.name, driver_cls.version)

    def register_device(self, device: DeviceInfo) -> Optional[DeviceDriver]:
        """Register hardware device and attempt automatic driver binding."""
        with self._lock:
            self._devices[device.device_id] = device

        return self.bind_driver(device.device_id)

    def bind_driver(self, device_id: str) -> Optional[DeviceDriver]:
        """Find and load compatible driver for a device."""
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return None
            if device.bound_driver and device.bound_driver in self._loaded_drivers:
                return self._loaded_drivers[device.bound_driver]

            # Find matching driver class
            matching_cls: Optional[Type[DeviceDriver]] = None
            for cls in self._driver_classes.values():
                dummy = cls()
                if dummy.probe(device):
                    matching_cls = cls
                    break

            if not matching_cls:
                logger.warning("DriverManager: No matching driver found for %s", device)
                return None

        # Load matched driver (outside lock to resolve dependencies cleanly)
        driver = self.load_driver(matching_cls.name)
        if driver:
            with self._lock:
                device.bound_driver = driver.name
                driver.init(device)
                driver.start()
                logger.info("DriverManager: Bound %s to driver '%s'", device, driver.name)
            return driver
        return None

    def load_driver(self, driver_name: str) -> Optional[DeviceDriver]:
        """Load and start a driver, automatically resolving and loading dependencies."""
        with self._lock:
            if driver_name in self._loaded_drivers:
                return self._loaded_drivers[driver_name]

            if driver_name not in self._driver_classes:
                logger.error("DriverManager: Driver '%s' not registered", driver_name)
                return None

            driver_cls = self._driver_classes[driver_name]

        # Resolve dependencies
        for dep in driver_cls.dependencies:
            if not self.load_driver(dep):
                logger.error("DriverManager: Failed to load dependency '%s' for '%s'", dep, driver_name)
                return None

        with self._lock:
            driver = driver_cls()
            # Setup NJ Fault Domain cage for this driver
            cage = NJFaultDomain(
                f"Driver_{driver_name}",
                failure_threshold=3,
                fallback_fn=lambda exc, snap: exc
            )
            self._driver_cages[driver_name] = cage

            # Initialize and start within cage
            success, _ = cage.execute(driver.start)
            if not success:
                logger.error("DriverManager: Driver '%s' failed start hook", driver_name)
                driver.state = DriverState.FAULTED
                return None

            self._loaded_drivers[driver_name] = driver
            logger.info("DriverManager: Driver '%s' loaded and RUNNING", driver_name)
            return driver

    def unload_driver(self, driver_name: str, force: bool = False) -> bool:
        """Safely stop and unload a driver, ensuring no dependents are active."""
        with self._lock:
            if driver_name not in self._loaded_drivers:
                return False

            # Check if other loaded drivers depend on this one
            if not force:
                for active_name, active_drv in self._loaded_drivers.items():
                    if active_name != driver_name and driver_name in active_drv.dependencies:
                        logger.error(
                            "DriverManager: Cannot unload '%s', active driver '%s' depends on it",
                            driver_name, active_name
                        )
                        return False

            driver = self._loaded_drivers[driver_name]
            cage = self._driver_cages.get(driver_name)

        # Stop and unload within cage
        if cage:
            cage.execute(driver.stop)
            cage.execute(driver.unload)
        else:
            driver.stop()
            driver.unload()

        with self._lock:
            # Unbind any devices
            for dev in self._devices.values():
                if dev.bound_driver == driver_name:
                    dev.bound_driver = None

            del self._loaded_drivers[driver_name]
            if driver_name in self._driver_cages:
                del self._driver_cages[driver_name]

            logger.info("DriverManager: Driver '%s' unloaded successfully", driver_name)
            return True

    def safe_io(
        self,
        driver_name: str,
        io_func: Callable[[DeviceDriver], Any]
    ) -> Tuple[bool, Any]:
        """
        Execute I/O operation on a driver safely inside its NJ Fault Cage.
        Protects the kernel from hardware driver exceptions and crashes.
        """
        with self._lock:
            driver = self._loaded_drivers.get(driver_name)
            cage = self._driver_cages.get(driver_name)

        if not driver:
            return False, IOError(f"Driver '{driver_name}' is not loaded")

        if cage:
            return cage.execute(io_func, driver)
        else:
            try:
                res = io_func(driver)
                return True, res
            except Exception as e:
                return False, e

    def get_driver(self, name: str) -> Optional[DeviceDriver]:
        with self._lock:
            return self._loaded_drivers.get(name)

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        with self._lock:
            return self._devices.get(device_id)

    def list_drivers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": d.name,
                    "version": d.version,
                    "type": d.driver_type.name,
                    "state": d.state.name,
                    "bound_device": d.device.device_id if d.device else None,
                    "stats": d.stats,
                }
                for d in self._loaded_drivers.values()
            ]

    def list_devices(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "device_id": dev.device_id,
                    "class": dev.device_class.name,
                    "vendor_id": f"0x{dev.vendor_id:04x}",
                    "product_id": f"0x{dev.product_id:04x}",
                    "bus_address": dev.bus_address,
                    "bound_driver": dev.bound_driver,
                }
                for dev in self._devices.values()
            ]
