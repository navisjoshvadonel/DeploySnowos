# SnowOS Update & Recovery Strategy

SnowOS treats updates and system recovery as a single, unified problem space. Updates must be atomic, invisible, and perfectly safe. Recovery must be instant.

## The Atomic Update Flow
SnowOS abandons the traditional `apt upgrade` experience for end-users.

1. **Background Fetching:** `snowos-updater` continuously checks for updates in the background. This includes security patches from the Ubuntu LTS repos, feature updates from SnowOS, and new AI model weights.
2. **Snapshot Creation:** Before any modification happens, a BTRFS snapshot of the active root (`/`) is taken.
3. **Staging:** Updates are applied to an isolated staging environment or directly to the live system *after* the snapshot is secured.
4. **Validation:** The system runs a quick sanity check (verifying critical dependencies and daemon configurations).
5. **Reboot/Apply:** For core updates, the user is prompted to restart. The system boots into the updated state.

## The Rollback Engine
If an update causes a kernel panic, breaks the display server, or corrupts a core library, the user is never left with a broken system.

- **Automated Rollback:** If `snowos-sentinel` detects a failure to reach the graphical target during boot (e.g., 3 consecutive crashes of the Frost Shell), it automatically triggers the GRUB integration to boot the previous "Last Known Good" BTRFS snapshot.
- **Manual Rollback:** The user can select `SnowOS Recovery` in the customized boot menu to manually select a snapshot or run `snowos rollback` from the CLI.

## Immutable-Ready Architecture
While initially running on a standard RW filesystem, the update mechanism paves the way for an immutable layout:
- The system partitions will be mounted Read-Only.
- Updates will be delivered as full OS images (e.g., using OSTree or a custom SquashFS overlay mechanism) rather than individual deb packages.
- User data and AI state will remain on persistent, writable subvolumes (`/home`, `/var/lib/snowos-ai`).
