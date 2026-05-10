# SnowOS Package & Repository Strategy

To maintain independence while utilizing the robust Ubuntu LTS package ecosystem, SnowOS employs a hybrid repository strategy.

## 1. The Core Repository Strategy
- **Base Packages:** `ubuntu-base` is used instead of `ubuntu-desktop`. This prevents the installation of GNOME, Canonical's custom branding, and generic snaps by default.
- **SnowOS PPA/Repository:** SnowOS maintains its own APT repository (or localized deb packages during the ISO build) that holds the Frost Shell, AI Core services, and the SnowOS CLI.
- **Overrides:** The SnowOS repository provides higher-epoch versions of specific packages like `base-files`, `os-release`, `grub2-themes`, and `plymouth-theme-snowos` to aggressively overwrite Ubuntu branding.

## 2. Package Masking
To prevent the Ubuntu ecosystem from accidentally "reverting" our identity during an `apt upgrade`, SnowOS masks or holds certain packages:
- `ubuntu-desktop` and `ubuntu-desktop-minimal` are pinned to negative priority so they are never installed.
- `snapd` is strictly controlled or replaced entirely by Flatpak for GUI applications, as Snaps often tightly integrate with the Ubuntu identity.

## 3. Atomic Update Management (`snowos update`)
Users will never run `apt update` directly. The `snowos` CLI manages updates:
1. **Snapshot:** Takes a BTRFS snapshot of `/`.
2. **Fetch:** Pulls security patches from Ubuntu repos and feature updates from the SnowOS repo.
3. **Validate:** Ensures the update won't break the Frost Shell or AI Core dependencies.
4. **Apply & Rotate:** Installs the updates and updates the bootloader if necessary. If the system fails to boot, `snowos-sentinel` automatically rolls back to the pre-update snapshot.

## 4. Third-Party Software
Users will install software primarily via:
- **SnowOS App Center:** A curated interface prioritizing Flatpaks and AppImages.
- **Containers:** Native support for sandboxed dev environments.
