#!/bin/bash
# SnowOS Aurora Branding Rollback Script
# This script restores original Ubuntu branding and visuals.

set -e

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./rollback_branding.sh)"
  exit 1
fi

echo "--- Reverting SnowOS Aurora Branding ---"

# 1. Identity
rm -f /etc/os-release /etc/lsb-release
if dpkg-divert --list /etc/os-release | grep -q "diverted by snowos"; then
    dpkg-divert --remove --rename /etc/os-release
fi
if dpkg-divert --list /etc/lsb-release | grep -q "diverted by snowos"; then
    dpkg-divert --remove --rename /etc/lsb-release
fi

# 2. Visuals
rm -f /usr/share/pixmaps/snowos-logo.png
rm -f /usr/share/pixmaps/system-logo.png
rm -f /usr/share/backgrounds/snowos-wallpaper.png
rm -f /boot/grub/snowos-wallpaper.png

if command -v gsettings >/dev/null 2>&1; then
    gsettings set org.gnome.desktop.interface icon-theme "Yaru" || true
    gsettings set org.gnome.desktop.interface gtk-theme "Yaru" || true
fi

# 3. GRUB
rm -f /etc/default/grub.d/50-snowos.cfg
if [ -f /etc/default/grub ]; then
    sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR=`( . \/etc\/os-release; echo ${NAME:-Ubuntu} ) 2>\/dev\/null || echo Ubuntu`/' /etc/default/grub
    sed -i '\|^GRUB_BACKGROUND=.*snowos-wallpaper.png.*|d' /etc/default/grub
fi
if command -v update-grub >/dev/null 2>&1; then
    update-grub || true
fi

# 4. Banners
echo -e "Ubuntu 24.04.4 LTS \\n \\l\n" > /etc/issue
echo "Ubuntu 24.04.4 LTS" > /etc/issue.net

echo "--- Reversion complete ---"
