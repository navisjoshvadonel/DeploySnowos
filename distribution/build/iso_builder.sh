#!/bin/bash
# SnowOS ISO Builder Pipeline
# This script uses live-build to generate a custom SnowOS ISO.

set -e

BUILD_DIR="build-env"
IDENTITY_DIR="../identity"

echo "Initializing SnowOS ISO Build Pipeline..."

# Ensure we have the required tools
if ! command -v lb &> /dev/null; then
    echo "Error: live-build is not installed. Please run: sudo apt install live-build"
    exit 1
fi

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "Configuring live-build for SnowOS..."
lb config \
    --distribution jammy \
    --architecture amd64 \
    --archive-areas "main restricted universe multiverse" \
    --linux-flavours generic \
    --bootappend-live "boot=casper quiet splash noautologin" \
    --iso-application "SnowOS" \
    --iso-publisher "SnowOS Development Team" \
    --iso-volume "SnowOS_Aurora" \
    --memtest none

echo "Creating package lists..."
mkdir -p config/package-lists
# We install ubuntu-base, Xorg, and our dependencies. We EXCLUDE ubuntu-desktop.
cat <<EOF > config/package-lists/snowos.list.chroot
ubuntu-base
xorg
wayland-protocols
btrfs-progs
systemd
systemd-sysv
network-manager
pipewire
python3
python3-pip
grub-efi-amd64
plymouth
plymouth-theme-spinner
calamares
EOF

echo "Injecting Custom Identity and Hooks..."
mkdir -p config/hooks/normal
cp ../chroot_hooks.sh config/hooks/normal/01-snowos-setup.hook.chroot
chmod +x config/hooks/normal/01-snowos-setup.hook.chroot

mkdir -p config/includes.chroot/etc
cp $IDENTITY_DIR/os-release config/includes.chroot/etc/os-release

echo "Build configuration complete."
echo "To build the ISO, run: sudo lb build"
echo "(Note: This process takes significant time and requires root privileges.)"
