# Installing SnowOS

SnowOS installs as a branded Ubuntu platform layer with separate `core` and `visual` profiles.

## Prerequisites

- Ubuntu 24.04 LTS or a compatible newer Ubuntu release
- `sudo` access
- Python 3 available on the system

## Install Modes

### Core

Installs the SnowOS runtime, service units, platform config, and validation tooling.

```bash
sudo ./install.sh core
```

### Visual

Installs desktop-facing dependencies used by the SnowOS visual layer.

```bash
sudo ./install.sh visual
```

### Full

Installs both profiles.

```bash
sudo ./install.sh all
```

## What The Installer Sets Up

- Runtime code in `/opt/snowos`
- Platform config in `/etc/snowos`
- Runtime sockets in `/run/snowos`
- SnowOS service homes in `/var/lib/snowos`
- Boot status and feature flags in `/run/snowos`
- An integrity baseline in `/etc/snowos/integrity_manifest.json`
- SnowOS services through `systemd`

Core installation enables:

- `snowos-boot.service`
- `snowos-broker.service`
- `snowos-sentinel.service`
- `snowos-aicore.service`
- `snowos-control.service`

## Validation

Run:

```bash
python3 snowos-runtime/validation/check_health.py
```

If you intentionally change SnowOS policy or boot config files, rerun `sudo ./install.sh core` to refresh the integrity baseline.

## Uninstall

Run:

```bash
sudo ./snowos-runtime/uninstall.sh
```
