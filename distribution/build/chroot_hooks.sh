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

# 2. Setup AI Runtime Environment
echo "Setting up AI Runtime..."
mkdir -p /var/lib/snowos-ai
mkdir -p /opt/snowos/core
chmod 755 /opt/snowos/core

# 3. Configure Boot Experience
echo "Configuring GRUB and Plymouth..."
sed -i 's/GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="SnowOS"/g' /etc/default/grub
sed -i 's/quiet splash/quiet splash plymouth.ignore-serial-consoles/g' /etc/default/grub

# Enable the required SnowOS services (assuming they are injected into /etc/systemd/system)
# systemctl enable snowos-broker.service
# systemctl enable snowos-sentinel.service
# systemctl enable snowos-aicore.service
# systemctl enable snowos-control.service

# 4. Clean up Ubuntu references
echo "Removing Ubuntu specific branding..."
apt-get purge -y ubuntu-wallpapers* ubuntu-mono ubuntu-advantage-tools || true
apt-get autoremove -y
apt-get clean

echo "SnowOS Chroot Hook Complete."
