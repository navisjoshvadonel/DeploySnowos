#!/bin/bash
# SnowOS Chroot Hook
# This script runs inside the ISO chroot during the build process to finalize the SnowOS environment.

set -e

echo "Running SnowOS Chroot Setup Hook..."

# 1. Enforce Custom Identity
# We divert the default os-release so updates don't overwrite it
if [ ! -f /etc/os-release.ubuntu-default ]; then
    dpkg-divert --add --rename --divert /etc/os-release.ubuntu-default /etc/os-release
fi
# The custom os-release is injected via includes.chroot

# 2. Setup AI Runtime Environment & Install SnowOS
echo "Running SnowOS Offline Installer..."
if [ -f "/opt/snowos-installer/install.sh" ]; then
    cd /opt/snowos-installer
    chmod +x install.sh
    ./install.sh all --offline
    cd /
    
    echo "Cleaning up installer files..."
    rm -rf /opt/snowos-installer
else
    echo "WARNING: SnowOS installer not found in chroot!"
fi

# 3. Configure Boot Experience
echo "Configuring GRUB and Plymouth..."
sed -i 's/GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="SnowOS Aurora"/g' /etc/default/grub
sed -i 's/quiet splash/quiet splash plymouth.ignore-serial-consoles/g' /etc/default/grub

# 4. Clean up Ubuntu references
echo "Removing Ubuntu specific branding..."
apt-get purge -y ubuntu-wallpapers* ubuntu-mono ubuntu-advantage-tools || true
apt-get autoremove -y
apt-get clean

echo "SnowOS Chroot Hook Complete."
