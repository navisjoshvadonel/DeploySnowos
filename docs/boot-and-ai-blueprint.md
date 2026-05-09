# SnowOS Boot And AI Blueprint

SnowOS now has a dedicated boot contract so branding, trust, and AI posture are established before the rest of the platform starts.

## Core Files

- Boot profile config: `/etc/snowos/boot_manifest.json`
- AI feature catalog: `/etc/snowos/ai_features.json`
- Brand manifest: `/etc/snowos/brand.json`
- Integrity baseline: `/etc/snowos/integrity_manifest.json`
- Published boot status: `/run/snowos/boot-status.json`
- Published feature flags: `/run/snowos/feature-flags.json`

## Boot Flow

1. `snowos-boot.service` starts before broker, sentinel, control, and Nyx.
2. Runtime, state, and log directories are prepared.
3. `TrustBoot` validates tracked SnowOS assets against the integrity manifest.
4. A snapshot is taken when `SNOWOS_BOOT_TAKE_SNAPSHOT=1`.
5. The active boot profile resolves enabled AI features.
6. Boot status and feature flags are written for SnowControl and follow-on services.

## Boot Profiles

- `secure`: smallest surface area, strongest trust posture, guarded persona selection.
- `balanced`: daily driver profile with resume context and control-plane insight.
- `developer`: rich diagnostics, build coaching, offline reasoning cache, and plugin scouting.
- `immersive`: visual-first posture with branded ambience and ritualized startup identity.

## AI Feature Direction

The AI feature catalog is intentionally broader than what the runtime fully automates today. The current implementation already publishes and surfaces:

- profile-aware persona and mood selection
- integrity pulse and service preflight state
- workspace and context resume hints
- resource forecast and focus posture
- forensic recap data for degraded boots
- SnowControl insight files for live UI rendering

The catalog is also ready for continued expansion through features like `offline_reasoning_cache`, `memory_compass`, `intent_storyline`, and `focus_orchestrator`.

## Upgrade Guidance

- Use `sudo ./install.sh core` after runtime or config upgrades.
- Review `/run/snowos/boot-status.json` after first boot to confirm the selected profile and warnings.
- Turn on strict posture with `SNOWOS_BOOT_STRICT_INTEGRITY=1` once your tracked files are stable.
- If you intentionally edit tracked SnowOS config, rerun the installer to refresh `/etc/snowos/integrity_manifest.json`.
