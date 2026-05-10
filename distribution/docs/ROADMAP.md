# SnowOS Implementation Roadmap

This document outlines the phases to bring the SnowOS independent distribution to production.

## Phase 1: Core Distribution Infrastructure
- [ ] Establish `live-build` and `debootstrap` ISO generation pipeline.
- [ ] Strip Ubuntu identity (`os-release`, `plymouth`, `grub`).
- [ ] Create basic SnowOS custom branding overrides.
- [ ] Generate first bootable minimal ISO.

## Phase 2: Runtime Orchestration
- [ ] Implement systemd service units for `snowos-broker`, `snowos-sentinel`, `snowos-control`.
- [ ] Create the `snowos` CLI tool for system management.
- [ ] Implement atomic update mock logic.

## Phase 3: Frost Shell Prototype
- [ ] Build Wayland compositor skeleton.
- [ ] Implement glassmorphism UI framework (Qt/Slint).
- [ ] Create custom Login Manager (SnowDM).
- [ ] Integrate shell as default session in the ISO.

## Phase 4: AI Native Integration
- [ ] Integrate local LLM runtime (`snowos-aicore`).
- [ ] Implement AI Context Engine and desktop indexer.
- [ ] Build persistent AI overlay in the Frost Shell.
- [ ] Hook AI into `snowos-optimizer` for performance tuning.

## Phase 5: Immutability & Recovery
- [ ] Configure ISO installer (Calamares) to format BTRFS with subvolumes.
- [ ] Implement automated pre-update snapshots.
- [ ] Integrate snapshot boot options into GRUB.

## Phase 6: Polish & Release
- [ ] Finalize UI/UX animations.
- [ ] Conduct chaos testing on Sentinel recovery.
- [ ] Release Alpha 1 ISO to testers.
