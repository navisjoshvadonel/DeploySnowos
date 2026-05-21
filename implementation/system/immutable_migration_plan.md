# SnowOS Immutable Pivot Migration Plan

This document dictates the step-by-step architectural shift from a standard, mutable Ubuntu `/` filesystem to the hardened, immutable SnowOS layout.

## 1. Target Subvolume Structure

The system will format the main partition as BTRFS and create the following subvolumes:

```
@/ (Root BTRFS pool)
 ├── @system_current     -> Mounted at / (Read-Only)
 ├── @system_snapshot_1  -> Stored in /recovery
 ├── @runtime            -> Mounted at /runtime (tmpfs/overlay)
 ├── @user               -> Mounted at /user (LUKS Encrypted)
 └── @var                -> Mounted at /var (Logs, Caches)
```

## 2. Bootloader and Initramfs Changes

1. **GRUB Updates:** 
   Modify `grub.cfg` to explicitly boot from `@system_current` and append `ro` to the kernel arguments.
2. **Initramfs Hook:** 
   Write a custom `initramfs-tools` hook that mounts `@runtime` as an overlay on top of `/etc` and `/usr/local` to allow daemons to write PID/socket files without modifying the underlying OS.

## 3. Transactional Update Mechanism

Updates will no longer use `apt upgrade` directly on the live system.

1. `snowos-updater` creates a new BTRFS snapshot of `@system_current` called `@system_pending`.
2. The snapshot is mounted read-write in an isolated chroot.
3. `apt` or `flatpak` applies the updates exclusively to the chroot.
4. The snapshot is set to read-only.
5. The GRUB default boot target is switched to `@system_pending`.
6. Reboot. If `snowos-sentinel` detects a failure (3-strike rule), it reverts the GRUB target back to the previous snapshot.

## 4. Phased Migration Execution

- **Phase A:** Create `chroot_hooks.sh` to begin testing package installations in isolated snapshots.
- **Phase B:** Implement `rollback_controller.rs` to manage the BTRFS snapshot API.
- **Phase C:** Modify the `install.sh` script to force BTRFS subvolume creation instead of ext4.
- **Phase D:** Strip `/usr/bin/apt` from the user `$PATH` to enforce usage of `snowos-updater`.
