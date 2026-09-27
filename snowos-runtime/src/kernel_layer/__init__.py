"""
SnowOS Kernel Layer.
====================
Provides low-level operating system primitives:
  - performance: CPU scheduling (MLFQ), Virtual Memory, Deadlock-Free Sync Primitives, NJ Engine (Zero-copy IPC, Coalescing, Fault Isolation).
  - io_hardware: Device Driver Framework, Hardware Acceleration (TPU/GPU/SIMD), SnowFS Structured Filesystem.
  - predictive_optimizer: Autonomous proactive OS telemetry and tuning.
"""

from . import performance
from . import io_hardware

__all__ = ["performance", "io_hardware"]
