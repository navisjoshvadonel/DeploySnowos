# SnowOS Update Strategy

SnowOS uses a sophisticated, transparent update mechanism designed to ensure system stability and user convenience without relying directly on interactive `apt` commands.

## Architecture

1.  **The SnowOS Repository:** We maintain a dedicated repository for all custom SnowOS packages (the Frost Shell, AI Core, System Daemons, and branding overrides). This repository takes precedence over Ubuntu base repositories.
2.  **The CLI Tool:** The `snowos` command-line utility serves as the primary interface for system updates (`snowos update`).
3.  **The Background Daemon:** `snowos-updater.service` handles scheduled checks and silent downloads.

## Update Process

1.  **Verification:** The updater checks for available packages in both the SnowOS and Ubuntu security repositories.
2.  **Staging:** Updates are downloaded to a secure staging area.
3.  **Snapshotting:** Before any package is installed, a BTRFS snapshot of the current root filesystem is generated (managed in coordination with the Recovery Strategy).
4.  **Application:** Packages are installed. High-priority SnowOS packages explicitly overwrite any generic Ubuntu configuration files that may have been touched.
5.  **Reboot:** If core components (kernel, compositor, critical daemons) are updated, the user is seamlessly prompted to restart.

## Handling Upstream Changes

Since SnowOS relies on `ID_LIKE=ubuntu` for package compatibility, we must actively defend the system identity:
*   We use `dpkg-divert` or hold specific packages (like `base-files` and `ubuntu-desktop`) to prevent them from reverting our custom branding during a routine upgrade.
*   Security patches from Ubuntu LTS are applied transparently, ensuring a rock-solid foundation without compromising the custom UX.
