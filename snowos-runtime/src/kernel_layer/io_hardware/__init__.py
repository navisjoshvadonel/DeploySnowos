"""
SnowOS Kernel — Hardware Interfacing & I/O Subsystem
====================================================

Exports:
  - DeviceDriverFramework: DeviceDriver, DriverManager, DeviceInfo, DriverType, DriverState, VirtualRamDiskDriver, GPUDriver, TPUSystolicDriver
  - HardwareAcceleration: HardwareAccelerator, TPUSystolicAccelerator, GPUComputeAccelerator, CPUSimdAccelerator, AccelerationTier
  - SnowFS: SnowFS, BlockDevice, Inode, DirEntry, FileType, DataIntegrityError, FilesystemError
"""

from .driver_framework import (
    DeviceDriver,
    DriverManager,
    DeviceInfo,
    DriverType,
    DriverState,
    VirtualRamDiskDriver,
    GPUDriver,
    TPUSystolicDriver,
)

from .hardware_acceleration import (
    HardwareAccelerator,
    TPUSystolicAccelerator,
    GPUComputeAccelerator,
    CPUSimdAccelerator,
    AccelerationTier,
    TensorBuffer,
)

from .snow_fs import (
    SnowFS,
    BlockDevice,
    Inode,
    DirEntry,
    FileType,
    DataIntegrityError,
    FilesystemError,
)

__all__ = [
    "DeviceDriver",
    "DriverManager",
    "DeviceInfo",
    "DriverType",
    "DriverState",
    "VirtualRamDiskDriver",
    "GPUDriver",
    "TPUSystolicDriver",
    "HardwareAccelerator",
    "TPUSystolicAccelerator",
    "GPUComputeAccelerator",
    "CPUSimdAccelerator",
    "AccelerationTier",
    "TensorBuffer",
    "SnowFS",
    "BlockDevice",
    "Inode",
    "DirEntry",
    "FileType",
    "DataIntegrityError",
    "FilesystemError",
]
