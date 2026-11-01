#!/bin/bash
# SnowOS ISO Builder Pipeline
# This script uses live-build to generate a production-ready, VM-compatible SnowOS live hybrid ISO.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build-env"
IDENTITY_DIR="$REPO_ROOT/distribution/identity"
CALAMARES_SRC="$REPO_ROOT/distribution/calamares"
DISTRO="${SNOWOS_BASE_DISTRO:-noble}"

echo "=========================================================="
echo " ❄️  Initializing SnowOS Live ISO Build Pipeline"
echo " Target Distribution Base: ${DISTRO}"
echo " Architecture: amd64 (UEFI + BIOS Hybrid ISO)"
echo "=========================================================="

# Ensure we have the required tools
if ! command -v lb &> /dev/null; then
    echo "Error: live-build is not installed. Please run: sudo apt install -y live-build xorriso isolinux dosfstools mtools"
    exit 1
fi

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "Configuring live-build for SnowOS..."
lb config \
    --distribution "$DISTRO" \
    --architecture amd64 \
    --archive-areas "main restricted universe multiverse" \
    --linux-flavours generic \
    --bootappend-live "boot=casper quiet splash fsck.mode=skip" \
    --iso-application "SnowOS Aurora" \
    --iso-publisher "SnowOS Development Team" \
    --iso-volume "SnowOS_Aurora" \
    --binary-images iso-hybrid \
    --bootloaders "grub-efi,syslinux" \
    --memtest none

echo "Creating package lists..."
mkdir -p config/package-lists
cat <<EOF > config/package-lists/snowos.list.chroot
ubuntu-base
casper
discover
laptop-detect
os-prober
linux-image-generic
linux-headers-generic
linux-modules-extra-generic
grub-pc-bin
grub-efi-amd64
grub-efi-amd64-bin
grub-efi-amd64-signed
shim-signed
efibootmgr
dosfstools
mtools
xorriso
btrfs-progs
e2fsprogs
parted
util-linux
syslinux
isolinux
syslinux-common
xserver-xorg
xserver-xorg-video-all
xserver-xorg-input-all
virtualbox-guest-utils
qemu-guest-agent
systemd
systemd-sysv
network-manager
pipewire
pipewire-pulse
wireplumber
gnome-shell
gnome-session
gdm3
gnome-terminal
nautilus
sudo
python3
python3-pip
python3-psutil
python3-rich
python3-gi
python3-gi-cairo
gir1.2-gtk-3.0
scrot
xdotool
wmctrl
xbindkeys
brightnessctl
libnotify-bin
plymouth
plymouth-theme-spinner
calamares
calamares-settings-ubuntu
EOF

echo "Injecting Custom Identity and Hooks..."
mkdir -p config/hooks/normal
cp "$SCRIPT_DIR/chroot_hooks.sh" config/hooks/normal/01-snowos-setup.hook.chroot
chmod +x config/hooks/normal/01-snowos-setup.hook.chroot

mkdir -p config/includes.chroot/etc
if [ -f "$IDENTITY_DIR/os-release" ]; then
    cp "$IDENTITY_DIR/os-release" config/includes.chroot/etc/os-release
fi
if [ -f "$IDENTITY_DIR/lsb-release" ]; then
    cp "$IDENTITY_DIR/lsb-release" config/includes.chroot/etc/lsb-release
fi

# Pre-stage GRUB & Plymouth branding assets
mkdir -p config/includes.chroot/boot/grub config/includes.chroot/usr/share/backgrounds
if [ -f "$REPO_ROOT/assets/snowos-wallpaper.png" ]; then
    cp -f "$REPO_ROOT/assets/snowos-wallpaper.png" config/includes.chroot/boot/grub/snowos-wallpaper.png
    cp -f "$REPO_ROOT/assets/snowos-wallpaper.png" config/includes.chroot/usr/share/backgrounds/snowos-wallpaper.png
fi

# Pre-stage Calamares Installer Configuration
if [ -d "$CALAMARES_SRC" ]; then
    echo "Injecting SnowOS Calamares Installer configuration..."
    mkdir -p config/includes.chroot/etc/calamares
    cp -r "$CALAMARES_SRC"/* config/includes.chroot/etc/calamares/
    
    # Desktop installer shortcut for live session
    mkdir -p config/includes.chroot/etc/skel/Desktop config/includes.chroot/usr/share/applications
    if [ -f "$IDENTITY_DIR/install-snowos.desktop" ]; then
        cp "$IDENTITY_DIR/install-snowos.desktop" config/includes.chroot/usr/share/applications/
        cp "$IDENTITY_DIR/install-snowos.desktop" config/includes.chroot/etc/skel/Desktop/
        chmod +x config/includes.chroot/etc/skel/Desktop/install-snowos.desktop
    fi
fi

echo "Injecting SnowOS Installer into chroot..."
mkdir -p config/includes.chroot/opt/snowos-installer
(cd "$REPO_ROOT" && tar cf - --exclude=distribution/build/build-env --exclude=.git .) | (cd config/includes.chroot/opt/snowos-installer && tar xf -)

echo "=========================================================="
echo " ✔ SnowOS Live ISO Build configuration complete."
echo " To build the ISO image, run:"
echo "   cd distribution/build/build-env && sudo lb build"
echo " To test the resulting ISO in a VM:"
echo "   ../../tools/run_snowos_vm.sh live-image-amd64.hybrid.iso"
echo "=========================================================="
