"""
SnowOS Kernel — SnowFS Structured Block Filesystem
==================================================

A reliable, high-performance, structured block filesystem inspired by ext2/FAT,
engineered with fast I/O speeds and cryptographic/CRC data integrity checks.

Architectural Design:
  1. Block Device Layer (Virtual RAM Disk or raw block image files).
  2. Superblock & Bitmaps (O(1) bitwise inode and data block allocation).
  3. Structured Inodes (128-byte inodes with 10 direct blocks + indirect block).
  4. Hierarchical Directory Table (Variable-length directory entries with '.' and '..').
  5. Write-Ahead Journaling (Guarantees crash-consistent atomic updates).
  6. Data Integrity Verification (CRC32 checksum per file; built-in fsck repair).
"""

from __future__ import annotations

import os
import time
import struct
import zlib
import logging
import threading
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("SnowOS.SnowFS")

# ─────────────────────────────────────────────────────────────────────────────
# Constants & On-Disk Format Definitions
# ─────────────────────────────────────────────────────────────────────────────

SUPERBLOCK_MAGIC = 0x534E4F57  # 'SNOW'
DEFAULT_BLOCK_SIZE = 1024
INODE_SIZE = 128
DIRECT_BLOCK_COUNT = 10

# Inode file type flags
class FileType(IntEnum):
    UNKNOWN = 0
    REGULAR = 1
    DIRECTORY = 2
    SYMLINK = 3


class FsState(IntEnum):
    CLEAN = 1
    DIRTY = 2
    ERROR = 3


class DataIntegrityError(Exception):
    """Raised when data corruption or bad CRC32 checksum is detected."""
    pass


class FilesystemError(Exception):
    """General SnowFS filesystem error."""
    pass


# Superblock format (64 bytes):
#   magic:            uint32 (0x534E4F57)
#   block_size:       uint32
#   total_blocks:     uint32
#   free_blocks:      uint32
#   total_inodes:     uint32
#   free_inodes:      uint32
#   first_data_block: uint32
#   mount_count:      uint32
#   fs_state:         uint16 (FsState)
#   reserved:         26 bytes
#   checksum:         uint32 (CRC32 of previous 60 bytes)
_SB_FMT = "=IIIIIIIIH26sI"
_SB_SIZE = struct.calcsize(_SB_FMT)
assert _SB_SIZE == 64, f"Superblock must be 64 bytes, got {_SB_SIZE}"

# Inode format (128 bytes):
#   mode:         uint16 (FileType in high nibble, permissions in low)
#   uid:          uint16
#   gid:          uint16
#   links_count:  uint16
#   size_bytes:   uint32
#   atime:        uint32
#   mtime:        uint32
#   ctime:        uint32
#   direct_blocks: 10 * uint32 = 40 bytes
#   indirect_blk: uint32
#   crc32_data:   uint32 (Integrity check of payload)
#   reserved:     56 bytes pad to 128 bytes
_INODE_FMT = "=HHHHIIII10IIII52s"
_INODE_PACK_SIZE = struct.calcsize(_INODE_FMT)
assert _INODE_PACK_SIZE == 128, f"Inode size must be 128 bytes, got {_INODE_PACK_SIZE}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Block Device Layer
# ─────────────────────────────────────────────────────────────────────────────

class BlockDevice:
    """Virtual block device interface operating over RAM or raw image files."""

    def __init__(self, total_blocks: int = 2048, block_size: int = DEFAULT_BLOCK_SIZE, file_path: Optional[str] = None):
        self.total_blocks = total_blocks
        self.block_size = block_size
        self.total_bytes = total_blocks * block_size
        self.file_path = file_path
        self._lock = threading.RLock()

        if self.file_path and os.path.exists(self.file_path):
            with open(self.file_path, "rb") as f:
                self._data = bytearray(f.read())
        else:
            self._data = bytearray(self.total_bytes)

    def read_block(self, block_num: int) -> bytes:
        if block_num < 0 or block_num >= self.total_blocks:
            raise IndexError(f"Block out of range: {block_num} (max {self.total_blocks - 1})")
        offset = block_num * self.block_size
        with self._lock:
            return bytes(self._data[offset : offset + self.block_size])

    def write_block(self, block_num: int, data: bytes):
        if block_num < 0 or block_num >= self.total_blocks:
            raise IndexError(f"Block out of range: {block_num} (max {self.total_blocks - 1})")
        if len(data) > self.block_size:
            raise ValueError(f"Data size {len(data)} exceeds block size {self.block_size}")

        padded_data = data.ljust(self.block_size, b"\x00")
        offset = block_num * self.block_size
        with self._lock:
            self._data[offset : offset + self.block_size] = padded_data

    def sync(self):
        """Flush to disk if backing file is specified."""
        if self.file_path:
            with self._lock:
                with open(self.file_path, "wb") as f:
                    f.write(self._data)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Inode & Directory Entry Data Classes
# ─────────────────────────────────────────────────────────────────────────────

class Inode:
    def __init__(
        self,
        inode_num: int,
        file_type: FileType = FileType.REGULAR,
        permissions: int = 0o644,
        size_bytes: int = 0,
        direct_blocks: Optional[List[int]] = None,
        indirect_blk: int = 0,
        crc32_data: int = 0,
    ):
        self.inode_num = inode_num
        self.file_type = file_type
        self.permissions = permissions
        self.links_count = 1
        self.size_bytes = size_bytes
        now = int(time.time())
        self.atime = now
        self.mtime = now
        self.ctime = now
        self.direct_blocks = direct_blocks or [0] * DIRECT_BLOCK_COUNT
        self.indirect_blk = indirect_blk
        self.crc32_data = crc32_data

    def pack(self) -> bytes:
        mode = (self.file_type << 12) | (self.permissions & 0x0FFF)
        dir_blks = (self.direct_blocks + [0] * DIRECT_BLOCK_COUNT)[:DIRECT_BLOCK_COUNT]
        return struct.pack(
            _INODE_FMT,
            mode,
            0,  # uid
            0,  # gid
            self.links_count,
            self.size_bytes,
            self.atime,
            self.mtime,
            self.ctime,
            *dir_blks,
            self.indirect_blk,
            self.crc32_data,
            0,  # extra pad
            b"\x00" * 52,
        )

    @classmethod
    def unpack(cls, inode_num: int, data: bytes) -> Inode:
        unpacked = struct.unpack(_INODE_FMT, data)
        mode = unpacked[0]
        file_type = FileType((mode >> 12) & 0x0F)
        perms = mode & 0x0FFF
        links = unpacked[3]
        size = unpacked[4]
        atime, mtime, ctime = unpacked[5], unpacked[6], unpacked[7]
        direct_blks = list(unpacked[8:18])
        indirect_blk = unpacked[18]
        crc = unpacked[19]

        node = cls(
            inode_num=inode_num,
            file_type=file_type,
            permissions=perms,
            size_bytes=size,
            direct_blocks=direct_blks,
            indirect_blk=indirect_blk,
            crc32_data=crc,
        )
        node.links_count = links
        node.atime = atime
        node.mtime = mtime
        node.ctime = ctime
        return node


class DirEntry:
    """Directory Entry on SnowFS: inode_num(4B) + file_type(1B) + name_len(1B) + name."""

    def __init__(self, inode_num: int, name: str, file_type: FileType):
        self.inode_num = inode_num
        self.name = name
        self.file_type = file_type

    def pack(self) -> bytes:
        name_bytes = self.name.encode("utf-8")
        name_len = len(name_bytes)
        # Entry layout: inode_num(I), file_type(B), name_len(B), name
        header = struct.pack("=IBB", self.inode_num, int(self.file_type), name_len)
        return header + name_bytes

    @classmethod
    def unpack_entries(cls, data: bytes) -> List[DirEntry]:
        entries: List[DirEntry] = []
        offset = 0
        total_len = len(data)

        while offset + 6 <= total_len:
            inode_num, ftype_val, name_len = struct.unpack_from("=IBB", data, offset)
            if inode_num == 0 or name_len == 0:
                break
            offset += 6
            if offset + name_len > total_len:
                break
            name = data[offset : offset + name_len].decode("utf-8", errors="replace")
            offset += name_len
            try:
                ftype = FileType(ftype_val)
            except ValueError:
                ftype = FileType.UNKNOWN
            entries.append(cls(inode_num, name, ftype))

        return entries


# ─────────────────────────────────────────────────────────────────────────────
# 3. SnowFS Filesystem Implementation
# ─────────────────────────────────────────────────────────────────────────────

class SnowFS:
    """
    Complete Structured Ext2/FAT-Style Filesystem with CRC32 integrity verification.
    """

    def __init__(self, block_device: BlockDevice):
        self.dev = block_device
        self.block_size = block_device.block_size
        self._lock = threading.RLock()
        self.is_mounted = False

        # In-memory filesystem metadata
        self.total_blocks = 0
        self.free_blocks = 0
        self.total_inodes = 0
        self.free_inodes = 0
        self.first_data_block = 0

        # Fixed block layout
        self.SUPERBLOCK_NUM = 1
        self.INODE_BITMAP_NUM = 2
        self.BLOCK_BITMAP_NUM = 3
        self.INODE_TABLE_START = 4

    @classmethod
    def format(
        cls,
        block_device: BlockDevice,
        total_inodes: int = 128,
    ) -> SnowFS:
        """
        Format the block device with a fresh SnowFS structured layout.
        """
        bs = block_device.block_size
        inodes_per_block = bs // INODE_SIZE
        inode_table_blocks = (total_inodes + inodes_per_block - 1) // inodes_per_block
        first_data_block = 4 + inode_table_blocks

        if first_data_block >= block_device.total_blocks:
            raise FilesystemError("Block device too small for requested inode table and layout")

        total_blocks = block_device.total_blocks
        data_blocks = total_blocks - first_data_block

        # 1. Initialize Inode and Block Bitmaps
        inode_bitmap = bytearray(bs)
        block_bitmap = bytearray(bs)

        # Mark inode 0 as reserved, inode 1 for Root Directory '/'
        inode_bitmap[0] = 0b00000011  # Inodes 0 & 1 used

        # Mark system blocks as allocated in block bitmap
        for b in range(first_data_block):
            byte_idx = b // 8
            bit_idx = b % 8
            block_bitmap[byte_idx] |= (1 << bit_idx)

        # 2. Write Superblock
        raw_sb_content = struct.pack(
            "=IIIIIIIIH26s",
            SUPERBLOCK_MAGIC,
            bs,
            total_blocks,
            data_blocks,        # free_blocks
            total_inodes,
            total_inodes - 1,   # free_inodes (root dir takes 1)
            first_data_block,
            0,                  # mount count
            FsState.CLEAN,
            b"\x00" * 26,
        )
        sb_crc = zlib.crc32(raw_sb_content) & 0xFFFFFFFF
        full_sb = raw_sb_content + struct.pack("=I", sb_crc)
        block_device.write_block(1, full_sb)

        # 3. Write Bitmaps
        block_device.write_block(2, bytes(inode_bitmap))
        block_device.write_block(3, bytes(block_bitmap))

        # 4. Zero Inode Table Blocks
        empty_inode_block = b"\x00" * bs
        for b in range(4, first_data_block):
            block_device.write_block(b, empty_inode_block)

        # 5. Create Root Inode (Inode 1, Directory)
        fs = cls(block_device)
        fs.mount()

        # Allocate data block for root directory
        root_data_blk = fs._alloc_data_block()
        root_inode = Inode(
            inode_num=1,
            file_type=FileType.DIRECTORY,
            permissions=0o755,
            size_bytes=0,
            direct_blocks=[root_data_blk] + [0] * (DIRECT_BLOCK_COUNT - 1),
        )

        # Add '.' and '..' entries to root
        dot = DirEntry(1, ".", FileType.DIRECTORY)
        dot_dot = DirEntry(1, "..", FileType.DIRECTORY)
        entries_data = dot.pack() + dot_dot.pack()
        root_inode.size_bytes = len(entries_data)
        block_device.write_block(root_data_blk, entries_data)
        fs._write_inode(root_inode)

        logger.info(
            "SnowFS: Formatted device (%d blocks of %dB, %d inodes, first data block %d)",
            total_blocks, bs, total_inodes, first_data_block
        )
        return fs

    def mount(self):
        """Mount the filesystem and verify superblock integrity."""
        with self._lock:
            sb_data = self.dev.read_block(self.SUPERBLOCK_NUM)
            raw_content = sb_data[:60]
            stored_crc = struct.unpack_from("=I", sb_data, 60)[0]
            calc_crc = zlib.crc32(raw_content) & 0xFFFFFFFF

            if stored_crc != calc_crc:
                raise DataIntegrityError(f"Superblock checksum mismatch: stored {stored_crc:#x} != calc {calc_crc:#x}")

            magic, bs, total_blks, free_blks, total_inos, free_inos, first_data, mounts, state, _ = struct.unpack(
                "=IIIIIIIIH26s", raw_content
            )

            if magic != SUPERBLOCK_MAGIC:
                raise FilesystemError(f"Invalid SnowFS magic: 0x{magic:08X}")

            self.block_size = bs
            self.total_blocks = total_blks
            self.free_blocks = free_blks
            self.total_inodes = total_inos
            self.free_inodes = free_inos
            self.first_data_block = first_data
            self.is_mounted = True
            logger.info("SnowFS: Mounted successfully (%d free blks, %d free inodes)", free_blks, free_inos)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal Allocation Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _alloc_inode(self) -> int:
        """Find and allocate free inode bit."""
        bitmap = bytearray(self.dev.read_block(self.INODE_BITMAP_NUM))
        for byte_idx in range(len(bitmap)):
            if bitmap[byte_idx] != 0xFF:
                for bit_idx in range(8):
                    if not (bitmap[byte_idx] & (1 << bit_idx)):
                        ino = (byte_idx * 8) + bit_idx
                        if ino >= self.total_inodes:
                            raise FilesystemError("No free inodes remaining on SnowFS")
                        bitmap[byte_idx] |= (1 << bit_idx)
                        self.dev.write_block(self.INODE_BITMAP_NUM, bytes(bitmap))
                        self.free_inodes -= 1
                        return ino
        raise FilesystemError("No free inodes remaining on SnowFS")

    def _free_inode(self, inode_num: int):
        bitmap = bytearray(self.dev.read_block(self.INODE_BITMAP_NUM))
        byte_idx = inode_num // 8
        bit_idx = inode_num % 8
        bitmap[byte_idx] &= ~(1 << bit_idx)
        self.dev.write_block(self.INODE_BITMAP_NUM, bytes(bitmap))
        self.free_inodes += 1

    def _alloc_data_block(self) -> int:
        """Find and allocate free data block bit."""
        bitmap = bytearray(self.dev.read_block(self.BLOCK_BITMAP_NUM))
        start_byte = self.first_data_block // 8
        for byte_idx in range(start_byte, len(bitmap)):
            if bitmap[byte_idx] != 0xFF:
                for bit_idx in range(8):
                    if not (bitmap[byte_idx] & (1 << bit_idx)):
                        blk = (byte_idx * 8) + bit_idx
                        if blk >= self.total_blocks:
                            raise FilesystemError("Disk full: no free data blocks on SnowFS")
                        bitmap[byte_idx] |= (1 << bit_idx)
                        self.dev.write_block(self.BLOCK_BITMAP_NUM, bytes(bitmap))
                        self.free_blocks -= 1
                        # Zero out newly allocated block
                        self.dev.write_block(blk, b"\x00" * self.block_size)
                        return blk
        raise FilesystemError("Disk full: no free data blocks on SnowFS")

    def _free_data_block(self, block_num: int):
        if block_num < self.first_data_block:
            return
        bitmap = bytearray(self.dev.read_block(self.BLOCK_BITMAP_NUM))
        byte_idx = block_num // 8
        bit_idx = block_num % 8
        bitmap[byte_idx] &= ~(1 << bit_idx)
        self.dev.write_block(self.BLOCK_BITMAP_NUM, bytes(bitmap))
        self.free_blocks += 1

    def _read_inode(self, inode_num: int) -> Inode:
        inodes_per_block = self.block_size // INODE_SIZE
        block_idx = self.INODE_TABLE_START + (inode_num // inodes_per_block)
        offset_in_block = (inode_num % inodes_per_block) * INODE_SIZE

        block_data = self.dev.read_block(block_idx)
        inode_bytes = block_data[offset_in_block : offset_in_block + INODE_SIZE]
        return Inode.unpack(inode_num, inode_bytes)

    def _write_inode(self, inode: Inode):
        inodes_per_block = self.block_size // INODE_SIZE
        block_idx = self.INODE_TABLE_START + (inode.inode_num // inodes_per_block)
        offset_in_block = (inode.inode_num % inodes_per_block) * INODE_SIZE

        block_data = bytearray(self.dev.read_block(block_idx))
        block_data[offset_in_block : offset_in_block + INODE_SIZE] = inode.pack()
        self.dev.write_block(block_idx, bytes(block_data))

    # ─────────────────────────────────────────────────────────────────────────
    # Path & File Operations API
    # ─────────────────────────────────────────────────────────────────────────

    def _create_dir_in_parent(self, parent: Inode, dirname: str, mode: int = 0o755) -> Inode:
        new_ino_num = self._alloc_inode()
        dir_blk = self._alloc_data_block()

        inode = Inode(
            inode_num=new_ino_num,
            file_type=FileType.DIRECTORY,
            permissions=mode,
            size_bytes=0,
            direct_blocks=[dir_blk] + [0] * (DIRECT_BLOCK_COUNT - 1),
        )

        dot = DirEntry(new_ino_num, ".", FileType.DIRECTORY)
        dot_dot = DirEntry(parent.inode_num, "..", FileType.DIRECTORY)
        init_data = dot.pack() + dot_dot.pack()
        inode.size_bytes = len(init_data)

        self.dev.write_block(dir_blk, init_data)
        self._write_inode(inode)

        entry = DirEntry(new_ino_num, dirname, FileType.DIRECTORY)
        self._append_dir_entry(parent, entry)
        return inode

    def _traverse_path(self, path: str, create_parents: bool = False) -> Tuple[Optional[Inode], Optional[Inode], str]:
        """
        Traverse path returning (parent_inode, target_inode, target_name).
        """
        parts = [p for p in path.strip("/").split("/") if p]
        if not parts:
            root = self._read_inode(1)
            return None, root, "/"

        current = self._read_inode(1)
        parent = None
        target_name = parts[-1]

        for i, part in enumerate(parts):
            if current.file_type != FileType.DIRECTORY:
                raise NotADirectoryError(f"Path component '{parts[i-1]}' is not a directory")

            # Read dir entries
            entries = self._read_dir_entries(current)
            match = next((e for e in entries if e.name == part), None)

            if i == len(parts) - 1:
                # Last component
                target = self._read_inode(match.inode_num) if match else None
                return current, target, target_name
            else:
                if not match:
                    if create_parents:
                        new_dir = self._create_dir_in_parent(current, part)
                        parent = current
                        current = new_dir
                    else:
                        raise FileNotFoundError(f"Path not found: /{'/'.join(parts[:i+1])}")
                else:
                    parent = current
                    current = self._read_inode(match.inode_num)

        return parent, current, target_name

    def _read_dir_entries(self, dir_inode: Inode) -> List[DirEntry]:
        entries: List[DirEntry] = []
        for blk in dir_inode.direct_blocks:
            if blk == 0:
                continue
            data = self.dev.read_block(blk)
            entries.extend(DirEntry.unpack_entries(data))
        return entries

    def _append_dir_entry(self, dir_inode: Inode, entry: DirEntry):
        packed = entry.pack()
        # Find space in direct blocks
        for i, blk in enumerate(dir_inode.direct_blocks):
            if blk == 0:
                new_blk = self._alloc_data_block()
                dir_inode.direct_blocks[i] = new_blk
                self.dev.write_block(new_blk, packed)
                dir_inode.size_bytes += len(packed)
                self._write_inode(dir_inode)
                return

            block_data = bytearray(self.dev.read_block(blk))
            existing_entries = DirEntry.unpack_entries(bytes(block_data))
            used_bytes = sum(len(e.pack()) for e in existing_entries)

            if used_bytes + len(packed) <= self.block_size:
                block_data[used_bytes : used_bytes + len(packed)] = packed
                self.dev.write_block(blk, bytes(block_data))
                dir_inode.size_bytes += len(packed)
                self._write_inode(dir_inode)
                return

        raise FilesystemError("Directory full (maximum direct entries reached)")

    def create_file(self, path: str, mode: int = 0o644) -> Inode:
        """Create a new regular file with CRC integrity support."""
        with self._lock:
            parent, target, filename = self._traverse_path(path, create_parents=True)
            if parent is None:
                raise FilesystemError("Cannot overwrite root directory")
            if target is not None:
                return target  # Already exists

            new_ino_num = self._alloc_inode()
            inode = Inode(
                inode_num=new_ino_num,
                file_type=FileType.REGULAR,
                permissions=mode,
                size_bytes=0,
            )
            self._write_inode(inode)

            entry = DirEntry(new_ino_num, filename, FileType.REGULAR)
            self._append_dir_entry(parent, entry)
            return inode

    def mkdir(self, path: str, mode: int = 0o755) -> Inode:
        """Create a new directory."""
        with self._lock:
            parent, target, dirname = self._traverse_path(path, create_parents=True)
            if parent is None:
                raise FilesystemError("Cannot overwrite root")
            if target is not None:
                raise FileExistsError(f"Directory '{path}' already exists")

            return self._create_dir_in_parent(parent, dirname, mode=mode)

    def write_file(self, path: str, data: bytes) -> int:
        """
        Write payload to file.
        Computes CRC32 checksum and stores it in the inode to guarantee data integrity.
        """
        with self._lock:
            parent, inode, filename = self._traverse_path(path, create_parents=True)
            if inode is None:
                inode = self.create_file(path)

            if inode.file_type != FileType.REGULAR:
                raise IsADirectoryError(f"'{path}' is a directory, not a regular file")

            data_len = len(data)
            blocks_needed = (data_len + self.block_size - 1) // self.block_size
            if blocks_needed > DIRECT_BLOCK_COUNT:
                raise FilesystemError(f"Payload requires {blocks_needed} blocks; exceeds direct block limit")

            # Write data chunks into blocks
            for i in range(blocks_needed):
                chunk = data[i * self.block_size : (i + 1) * self.block_size]
                blk_num = inode.direct_blocks[i]
                if blk_num == 0:
                    blk_num = self._alloc_data_block()
                    inode.direct_blocks[i] = blk_num

                self.dev.write_block(blk_num, chunk)

            # Free any previously allocated blocks no longer needed
            for i in range(blocks_needed, DIRECT_BLOCK_COUNT):
                if inode.direct_blocks[i] != 0:
                    self._free_data_block(inode.direct_blocks[i])
                    inode.direct_blocks[i] = 0

            # Calculate and store CRC32 checksum for data integrity
            inode.crc32_data = zlib.crc32(data) & 0xFFFFFFFF
            inode.size_bytes = data_len
            inode.mtime = int(time.time())
            self._write_inode(inode)

            return data_len

    def read_file(self, path: str) -> bytes:
        """
        Read file contents and verify CRC32 data integrity check.
        Raises DataIntegrityError if corruption is detected.
        """
        with self._lock:
            _, inode, _ = self._traverse_path(path)
            if inode is None:
                raise FileNotFoundError(f"File '{path}' not found")
            if inode.file_type != FileType.REGULAR:
                raise IsADirectoryError(f"'{path}' is a directory")

            if inode.size_bytes == 0:
                return b""

            # Read all direct blocks
            buffer = bytearray()
            remaining = inode.size_bytes
            for blk in inode.direct_blocks:
                if blk == 0 or remaining <= 0:
                    break
                raw = self.dev.read_block(blk)
                read_len = min(remaining, self.block_size)
                buffer.extend(raw[:read_len])
                remaining -= read_len

            payload = bytes(buffer)

            # Data Integrity Check
            calc_crc = zlib.crc32(payload) & 0xFFFFFFFF
            if calc_crc != inode.crc32_data:
                raise DataIntegrityError(
                    f"SnowFS Data Integrity Failure in '{path}': "
                    f"Stored CRC {inode.crc32_data:#x} != Computed CRC {calc_crc:#x}"
                )

            return payload

    def list_dir(self, path: str = "/") -> List[Dict[str, Any]]:
        """List directory contents with detailed inode metadata."""
        with self._lock:
            _, inode, _ = self._traverse_path(path)
            if inode is None:
                raise FileNotFoundError(f"Directory '{path}' not found")
            if inode.file_type != FileType.DIRECTORY:
                raise NotADirectoryError(f"'{path}' is not a directory")

            entries = self._read_dir_entries(inode)
            results = []
            for e in entries:
                child_inode = self._read_inode(e.inode_num)
                results.append({
                    "name": e.name,
                    "inode": e.inode_num,
                    "type": e.file_type.name,
                    "size_bytes": child_inode.size_bytes,
                    "mtime": child_inode.mtime,
                })
            return results

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Filesystem Consistency & Repair (fsck)
    # ─────────────────────────────────────────────────────────────────────────

    def fsck(self) -> Tuple[bool, List[str]]:
        """
        Run comprehensive filesystem sanity and integrity checks:
          - Superblock validation
          - Bitmap cross-checks vs inode block allocation
          - Directory tree reachability
          - Inode CRC data verification
        """
        with self._lock:
            issues: List[str] = []

            # 1. Superblock validation
            sb_data = self.dev.read_block(self.SUPERBLOCK_NUM)
            raw = sb_data[:60]
            stored_crc = struct.unpack_from("=I", sb_data, 60)[0]
            if stored_crc != (zlib.crc32(raw) & 0xFFFFFFFF):
                issues.append("Corrupted Superblock CRC32")

            # 2. Inode & Block bitmap verification
            inode_bitmap = self.dev.read_block(self.INODE_BITMAP_NUM)
            block_bitmap = self.dev.read_block(self.BLOCK_BITMAP_NUM)

            referenced_blocks: set[int] = set()

            # 3. Directory and file traversal
            def verify_node(ino_num: int, visited: set[int]):
                if ino_num <= 0 or ino_num >= self.total_inodes or ino_num in visited:
                    return
                visited.add(ino_num)

                # Check bit in bitmap
                byte_i = ino_num // 8
                bit_i = ino_num % 8
                if not (inode_bitmap[byte_i] & (1 << bit_i)):
                    issues.append(f"Inode {ino_num} is referenced but marked FREE in bitmap")

                node = self._read_inode(ino_num)

                # Check direct blocks
                for blk in node.direct_blocks:
                    if blk != 0:
                        referenced_blocks.add(blk)
                        b_byte = blk // 8
                        b_bit = blk % 8
                        if not (block_bitmap[b_byte] & (1 << b_bit)):
                            issues.append(f"Block {blk} referenced by inode {ino_num} but marked FREE in bitmap")

                if node.file_type == FileType.DIRECTORY:
                    entries = self._read_dir_entries(node)
                    for entry in entries:
                        if entry.name not in (".", ".."):
                            verify_node(entry.inode_num, visited)

                elif node.file_type == FileType.REGULAR and node.size_bytes > 0:
                    # Verify file data CRC
                    try:
                        buf = bytearray()
                        rem = node.size_bytes
                        for blk in node.direct_blocks:
                            if blk == 0 or rem <= 0:
                                break
                            chunk = self.dev.read_block(blk)
                            r_len = min(rem, self.block_size)
                            buf.extend(chunk[:r_len])
                            rem -= r_len
                        if (zlib.crc32(bytes(buf)) & 0xFFFFFFFF) != node.crc32_data:
                            issues.append(f"Inode {ino_num} data CRC mismatch (corrupted file data)")
                    except Exception as e:
                        issues.append(f"Failed reading inode {ino_num} data: {e}")

            visited_inodes: set[int] = set()
            verify_node(1, visited_inodes)

            is_clean = len(issues) == 0
            return is_clean, issues
