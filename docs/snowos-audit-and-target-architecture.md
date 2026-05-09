# SnowOS Audit And Target Architecture

Note: this document captures the original sample audit and the intended target direction. Several of the highest-risk runtime and installer issues have since been addressed in the current upgraded SnowOS repo state.

## Executive Summary

The sample has a strong visual direction and a good instinct for separation of concerns, but the current implementation is a prototype overlay, not a secure operating environment.

The biggest gap is that the project claims "zero trust" behavior while several critical paths are fail-open, world-writable, hardcoded, or only simulated. The best outcome is to keep the SnowOS identity as a hardened Ubuntu distribution profile, not as a custom security substrate that replaces Ubuntu's own security model.

## What Is Good Already

- Clear visual identity across GTK, icons, dock, login, and terminal.
- Dedicated service users in the installer.
- Some systemd sandboxing is already present.
- The codebase is organized around layers, which is the right direction for long-term maintainability.
- Backups exist for desktop customization state, which is good for rollback.

## Critical Findings

### 1. The permission broker is not trustworthy yet

- `snowos-runtime/src/system_services/permission_broker/broker_daemon.py:26` makes the broker socket world-writable with `0o777`.
- `snowos-runtime/src/system_services/permission_broker/broker_daemon.py:56` returns a fixed prototype token instead of an actual scoped capability.
- `snowos-runtime/src/system_services/permission_broker/intent_validator.py:27-32` fails open when the sentinel is missing or errors.

Impact:
Any local process can potentially talk to the broker socket, and failure of the monitoring path becomes implicit allow.

### 2. The sentinel is also world-writable and heuristic-only

- `snowos-runtime/src/system_services/ai_sentinel/sentinel_daemon.py:23` sets the socket mode to `0o777`.
- `snowos-runtime/src/system_services/ai_sentinel/threat_model.py` only uses a simple request-rate heuristic plus a string match.

Impact:
This does not justify the repo's current "AI Sentinel" security claims. It is a demo classifier, not a security control.

### 3. The installer weakens debugging and opens permissions too broadly

- `install.sh:25-33` disables Apport and deletes crash artifacts globally.
- `install.sh:45-47` creates `/tmp/snowos_sockets` with mode `777`.
- `install.sh:35-36` mixes system customization and package installation into one root script without a profile model.

Impact:
The script removes useful incident data, broadens local attack surface, and makes rollback or auditing harder.

### 4. Documentation and runtime behavior do not match

- `docs/architecture.md:24` says all IPC uses `/tmp/snowos_sockets/`.
- `snowos-runtime/validation/check_health.py:24-25` checks raw sockets at `/tmp/snowos_broker.sock` and `/tmp/snowos_sentinel.sock`.

Impact:
The design contract is unclear, which makes hardening and operations harder.

### 5. A hardcoded local API key is shipped in the terminal tool

- `terminal/nyx/nyx.sh:12-15` sends commands to `http://localhost:4040/run` with a fixed `X-Nyx-Key`.

Impact:
This is credential leakage by design and should be treated as unsafe even for localhost-only tooling.

### 6. Customization scripts are brittle across machines and upgrades

- `snowos-runtime/src/scripts/install-motion.sh:10-11` and `:41` hardcode `/home/develop/...`.
- `snowos-runtime/src/scripts/apply-login-theme.sh` replaces GNOME shell theme resources directly.
- `snowos-runtime/src/scripts/install-visual-pack.sh:149-163` writes system-wide dconf overrides to bypass locks.

Impact:
This will break portability and make desktop upgrades fragile. Direct GDM resource replacement is especially high-maintenance.

## Best Outcome: What SnowOS Should Become

SnowOS should be a hardened Ubuntu distribution profile with a premium desktop layer, not a custom pseudo-kernel security framework.

### Recommended Positioning

- Base OS: Ubuntu 24.04 LTS or newer LTS.
- Security model: Ubuntu-native hardening first.
- App isolation: AppArmor plus strict snaps or tightly profiled services.
- Desktop customization: user-level GNOME theming, supported extensions, and reversible overrides.
- Optional compliance mode: Ubuntu Pro plus USG profiles for workstation or server.

## Target Architecture

### 1. Base Platform

- Use Ubuntu LTS with Secure Boot enabled.
- Use LUKS full-disk encryption. Prefer TPM-backed workflow only where supported and operationally acceptable.
- Keep automatic security updates on.
- Use Wayland by default.

### 2. Security Baseline

- Enforce AppArmor for SnowOS services and custom apps.
- Default-deny inbound firewall with `ufw` or `nftables`.
- Use separate Unix users per daemon or `DynamicUser=yes` where possible.
- Replace ad-hoc socket auth with Unix permissions plus signed or short-lived tokens.
- Store secrets in a proper system secret path, not in shell scripts.

### 3. Service Hardening

Every long-running daemon should use a stronger systemd profile:

- `DynamicUser=yes` when practical.
- `ProtectSystem=strict`
- `ProtectHome=yes` or `read-only`
- `PrivateTmp=yes`
- `NoNewPrivileges=yes`
- `PrivateDevices=yes`
- `ProtectControlGroups=yes`
- `ProtectKernelTunables=yes`
- `ProtectKernelModules=yes`
- `RestrictAddressFamilies=AF_UNIX` unless network is required
- `SystemCallArchitectures=native`
- `RestrictNamespaces=yes`
- `RestrictSUIDSGID=yes`
- `ReadWritePaths=` only for the exact runtime directory needed

### 4. IPC Model

- Move sockets from raw `/tmp/*.sock` paths to a dedicated runtime directory like `/run/snowos/`.
- Owner should be the service user or a dedicated group.
- Socket mode should be `0660`, not `0777`.
- Use systemd socket activation where possible.
- Make the broker fail closed.

### 5. Desktop Customization Model

- Keep GTK theme, icon theme, cursor theme, wallpaper, dock layout, and terminal prompt.
- Avoid patching GDM resources unless you accept version-specific maintenance.
- Prefer supported GNOME extensions and user-scoped settings over system-wide overrides.
- Make every customization reversible with a clean uninstall path.
- Separate "visual pack" from "security pack" entirely.

### 6. Performance Model

- Do not market `renice` and preload tricks as core security or OS intelligence.
- Use measured improvements only:
  - boot profiling
  - service startup trimming
  - package minimization
  - power-profile tuning
  - I/O scheduler and zram decisions based on hardware class
- Only keep daemons that produce measurable value.

## Recommended Product Split

### SnowOS Core

- Hardened Ubuntu profile
- Service units
- AppArmor policies
- Firewall profile
- Update policy
- Audit and health tooling

### SnowOS Visual Pack

- GTK theme
- Icon theme
- Cursor theme
- Wallpapers
- Dock and shell presets
- Login theme as an optional unsupported add-on

### SnowOS Control

- Read-only dashboard for health, policy status, updates, and audit results
- No direct authority without authenticated, auditable actions

## Practical Rebuild Plan

### Phase 1: Make the current sample honest and safe

- Remove "zero trust OS" claims from README until the enforcement path is real.
- Eliminate all `777` permissions.
- Remove hardcoded keys and absolute `/home/develop/...` paths.
- Separate installer modes:
  - `core`
  - `visual`
  - `dev`
- Stop disabling Apport by default.

### Phase 2: Rebuild enforcement on Ubuntu primitives

- Add AppArmor profiles for each service.
- Move runtime state into `/run/snowos`, `/var/lib/snowos`, and `/var/log/snowos`.
- Add hardened systemd unit options everywhere.
- Replace the prototype token flow with verifiable short-lived tokens.
- Make sentinel absence a deny condition for protected actions.

### Phase 3: Stabilize the desktop experience

- Convert all customization scripts to machine-agnostic paths.
- Keep user-level GNOME customization reversible.
- Treat GDM theming as optional and version-pinned.
- Add explicit backup and restore commands for every theme action.

### Phase 4: Offer real hardening profiles

- Baseline desktop profile
- Developer workstation profile
- High-security workstation profile
- Kiosk or appliance profile

## The Best Final Direction

If the goal is "best optimized customization and best secured Ubuntu from top to bottom", the strongest version of this project is:

Ubuntu LTS + Secure Boot + LUKS + AppArmor + unattended security updates + systemd hardening + UFW/nftables + optional Ubuntu Pro/USG hardening + a reversible SnowOS visual layer.

That combination is materially stronger, easier to maintain, and more credible than a custom broker-and-sentinel security story built mostly in Python user space.
