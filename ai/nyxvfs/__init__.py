"""
NyxVFS — Neural Virtual File System for SnowOS.
Treats the filesystem as a semantic vector space.
"""
from .vfs_engine import NyxVFS
from .healing_bridge import NyxHealingServer

__all__ = ["NyxVFS", "NyxHealingServer"]
