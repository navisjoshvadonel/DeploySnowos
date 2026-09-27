# Installing SnowOS

SnowOS installs as a branded Ubuntu platform layer with modular `core` and `visual` profiles, full pre-flight validation, and transactional rollback.

## Prerequisites

- **Base OS**: Ubuntu 22.04 LTS or 24.04 LTS
- **Permissions**: Root (`sudo`) privileges
- **Memory**: Minimum 2 GB RAM (4 GB recommended)
- **Disk**: Minimum 2 GB free disk space (5 GB recommended)
- **Python**: Python 3.10+

## Installation Modes

### Option 1: Interactive Unified Installer Dashboard (Recommended)

Launches the interactive CLI with pre-flight checks, live progress, and health diagnostics:

```bash
sudo python3 installer.py
```

### Option 2: Scripted / Headless Installation (`install.sh`)

#### Core Profile
Installs the SnowOS runtime, hardened service units, access policies, platform configs, and validation tooling:

```bash
sudo ./install.sh core
```

#### Visual Profile
Installs the Digital Frost desktop layer (icons, wallpapers, lockscreen theme, and GRUB identity):

```bash
sudo ./install.sh visual
```

#### Full Platform
Installs both Core and Visual profiles:

```bash
sudo ./install.sh all
```

#### Installation Flags
- `--offline`: Skip remote APT and pip package updates; use local/cached resources.
- `--auto-rollback`: Automatically revert changes if a critical service or step fails.
- `--skip-preflight`: Skip pre-flight system requirement diagnostics.
- `--rollback`: Revert all SnowOS modifications and restore baseline system state.

## What The Installer Sets Up

- Runtime code in `/opt/snowos`
- Platform config in `/etc/snowos`
- HMAC broker signing secrets in `/etc/snowos/secrets` (mode `0700`, owner `snowos-sys:snowos-sys`)
- Volatile runtime sockets in `/run/snowos` (mode `0775`)
- Dedicated service users: `snowos-sys` and `snowos-ai`
- Integrity baseline in `/etc/snowos/integrity_manifest.json`
- CLI management binary `/usr/local/bin/snowos`

### Strictly Ordered Services Sequence

1. `snowos-boot.service` (oneshot orchestrator)
2. `snowos-broker.service` (permission broker daemon)
3. `snowos-sentinel.service` (AI sentinel watchdog)
4. `snowos-aicore.service` (intelligence layer)
5. `snowos-control.service` (SnowControl management API)
6. `snowos-optimizer.service` & `snowos-updater.service`

## Validation & Diagnostics

Run the real-time health verification tool:

```bash
snowos doctor
```

Or execute the Python health check directly:

```bash
python3 snowos-runtime/validation/check_health.py
```

## System Rollback & Clean Uninstallation

To cleanly and safely revert all system services, diverted identity files, GNOME themes, and configuration trees back to pristine Ubuntu:

```bash
sudo ./rollback.sh
```
Or:
```bash
sudo ./install.sh --rollback
```
