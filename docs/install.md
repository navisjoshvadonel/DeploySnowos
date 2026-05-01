# Installing SnowOS Runtime Overlay

This guide covers installing the SnowOS v0.1 Runtime on top of a standard Ubuntu distribution.

## Prerequisites
- A clean installation of Ubuntu 24.04 (or similar Debian-based distro).
- Root (`sudo`) privileges.
- Python 3.10+ installed.

## Installation Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/snowos/core.git
   cd core
   ```

2. **Run the Installer**
   The installer script requires root privileges to configure `systemd` and create the dedicated system users (`snowos-sys` and `snowos-ai`).
   ```bash
   sudo ./install.sh
   ```
   *Note: This script will move the codebase to `/opt/snowos`, setup the IPC sockets in `/tmp`, and register the 5 core systemd services.*

3. **Verify the Deployment**
   Once installed, run the health check suite to ensure all daemons booted successfully and the Zero Trust sockets are active:
   ```bash
   python3 snowos-runtime/validation/check_health.py
   ```

## Starting the UI
For v0.1, the SnowControl dashboard runs as an application overlay. Start it via:
```bash
python3 /opt/snowos/app_layer/snow_control/backend/server.py
```

## Uninstallation
If you need to remove SnowOS and restore vanilla Ubuntu, simply run the rollback script:
```bash
sudo ./snowos-runtime/uninstall.sh
```
This will gracefully stop all services, delete the system users, and remove the `/opt/snowos` directory.
