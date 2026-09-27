#!/usr/bin/env bash
# ==============================================================================
# ❄️ SnowOS Transactional Rollback & Cleanup Utility
# Restores original Ubuntu system identity, services, configs, and visual theme.
# ==============================================================================

set -uo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "[-] Error: Rollback must be run as root (e.g. sudo ./rollback.sh)"
  exit 1
fi

echo "=========================================="
echo " ❄️  Initiating SnowOS System Rollback"
echo "=========================================="

# 1. Stop and disable all SnowOS systemd services
echo "[*] Step 1: Halting and disabling SnowOS system services..."
SNOWOS_SERVICES=(
  "snowos-frostbite.service"
  "snowos-healbridge.service"
  "snowos-governor.service"
  "snowos-nyxvfs.service"
  "snowos-updater.service"
  "snowos-optimizer.service"
  "snowos-control.service"
  "snowos-aicore.service"
  "snowos-sentinel.service"
  "snowos-broker.service"
  "snowos-boot.service"
)

for svc in "${SNOWOS_SERVICES[@]}"; do
  if systemctl list-unit-files "$svc" >/dev/null 2>&1; then
    echo "    - Stopping and disabling $svc..."
    systemctl stop "$svc" >/dev/null 2>&1 || true
    systemctl disable "$svc" >/dev/null 2>&1 || true
  fi
done

# Remove service unit files
echo "[*] Step 2: Removing systemd service units..."
rm -f /etc/systemd/system/snowos-*.service
systemctl daemon-reload || true
systemctl reset-failed || true

# Remove tmpfiles configuration
rm -f /etc/tmpfiles.d/snowos.conf

# 2. Revert Identity & Branding Diversions
echo "[*] Step 3: Reverting OS identity diversions and branding..."
rm -f /etc/os-release /etc/lsb-release

if command -v dpkg-divert >/dev/null 2>&1; then
  if dpkg-divert --list /etc/os-release | grep -q "diverted by snowos"; then
    echo "    - Restoring original /etc/os-release..."
    dpkg-divert --remove --rename /etc/os-release || true
  fi
  if dpkg-divert --list /etc/lsb-release | grep -q "diverted by snowos"; then
    echo "    - Restoring original /etc/lsb-release..."
    dpkg-divert --remove --rename /etc/lsb-release || true
  fi
fi

# Fallback: if /etc/os-release is still missing, recreate from upstream /usr/lib/os-release
if [ ! -f /etc/os-release ] && [ -f /usr/lib/os-release ]; then
  cp -p /usr/lib/os-release /etc/os-release
fi

if [ -L /usr/lib/os-release ] && [ -f /usr/lib/os-release.bak ]; then
  mv -f /usr/lib/os-release.bak /usr/lib/os-release
fi

# Revert issue banners
if [ -f /etc/issue.snowos.bak ]; then
  mv -f /etc/issue.snowos.bak /etc/issue
else
  echo -e "Ubuntu 24.04 LTS \\n \\l\n" > /etc/issue
fi

if [ -f /etc/issue.net.snowos.bak ]; then
  mv -f /etc/issue.net.snowos.bak /etc/issue.net
else
  echo "Ubuntu 24.04 LTS" > /etc/issue.net
fi

# 3. Revert Plymouth Boot Splash
echo "[*] Step 4: Restoring Plymouth boot splash..."
PLYMOUTH_SPINNER_DIR="/usr/share/plymouth/themes/spinner"
if [ -f "${PLYMOUTH_SPINNER_DIR}/watermark.png.bak" ]; then
  mv -f "${PLYMOUTH_SPINNER_DIR}/watermark.png.bak" "${PLYMOUTH_SPINNER_DIR}/watermark.png"
  if command -v update-initramfs >/dev/null 2>&1; then
    update-initramfs -u >/dev/null 2>&1 || true
  fi
fi

# 4. Revert GRUB Configuration
echo "[*] Step 5: Reverting GRUB settings..."
if [ -f /etc/default/grub.snowos.bak ]; then
  echo "    - Restoring GRUB from backup /etc/default/grub.snowos.bak..."
  cp -p /etc/default/grub.snowos.bak /etc/default/grub
else
  if [ -f /etc/default/grub ]; then
    sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR=`( . \/etc\/os-release; echo ${NAME:-Ubuntu} ) 2>\/dev\/null || echo Ubuntu`/' /etc/default/grub
    sed -i '\|^GRUB_BACKGROUND=.*snowos-wallpaper.png.*|d' /etc/default/grub
  fi
fi
if command -v update-grub >/dev/null 2>&1; then
  update-grub >/dev/null 2>&1 || true
fi

# 5. Revert Desktop Theming & Pixmaps
echo "[*] Step 6: Restoring desktop styling and pixmaps..."
rm -f /usr/share/pixmaps/snowos-logo.png
rm -f /usr/share/pixmaps/system-logo.png
rm -f /usr/share/backgrounds/snowos-wallpaper.png

TARGET_USER="${SUDO_USER:-$USER}"
if [ "$TARGET_USER" != "root" ] && id "$TARGET_USER" >/dev/null 2>&1; then
  USER_ID=$(id -u "$TARGET_USER")
  DBUS_ADDR="unix:path=/run/user/${USER_ID}/bus"
  if [ -S "/run/user/${USER_ID}/bus" ] && command -v gsettings >/dev/null 2>&1; then
    sudo -u "$TARGET_USER" DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" gsettings set org.gnome.desktop.interface icon-theme "Yaru" >/dev/null 2>&1 || true
    sudo -u "$TARGET_USER" DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" gsettings set org.gnome.desktop.interface gtk-theme "Yaru" >/dev/null 2>&1 || true
  fi
fi

# 6. Remove Installed CLI Tools & App Launchers
echo "[*] Step 7: Removing SnowOS binaries and desktop entries..."
rm -f /usr/local/bin/snowos
rm -f /usr/local/bin/snowos-pkg
rm -f /usr/share/applications/frostshell.desktop
if [ -f /etc/bash.bashrc ]; then
  sed -i '/alias apt=.snowos-pkg./d' /etc/bash.bashrc
fi

# 7. Remove Runtime & Configuration Trees
echo "[*] Step 8: Purging runtime and configuration trees..."
rm -rf /opt/snowos
rm -rf /etc/snowos
rm -rf /run/snowos
rm -rf /var/lib/snowos
rm -rf /var/log/snowos

# 8. Clean up service accounts
echo "[*] Step 9: Removing service accounts..."
for user in snowos-sys snowos-ai; do
  if id -u "$user" >/dev/null 2>&1; then
    userdel -r "$user" >/dev/null 2>&1 || userdel "$user" >/dev/null 2>&1 || true
  fi
  if getent group "$user" >/dev/null 2>&1; then
    groupdel "$user" >/dev/null 2>&1 || true
  fi
done

echo "=========================================="
echo " ✔ SnowOS Rollback Complete. Baseline Restored."
echo "=========================================="
exit 0
