#!/bin/bash
# SnowOS Chroot Hook
# Runs inside the ISO chroot during live-build to configure SnowOS runtime & boot reliability.

set -e

echo "Running SnowOS Chroot Setup Hook..."

# 1. Enforce Custom Identity
if [ ! -f /etc/os-release.ubuntu-default ]; then
    dpkg-divert --add --rename --divert /etc/os-release.ubuntu-default /etc/os-release || true
fi

# 2. Setup AI Runtime Environment & Install SnowOS
echo "Running SnowOS Offline Installer..."
if [ -f "/opt/snowos-installer/install.sh" ]; then
    cd /opt/snowos-installer
    chmod +x install.sh
    ./install.sh all --offline --skip-preflight || {
        echo "[-] Warning: SnowOS installer reported non-zero status in chroot; continuing with base assets..."
    }
    cd /
    
    echo "Cleaning up installer temporary files..."
    rm -rf /opt/snowos-installer
else
    echo "WARNING: SnowOS installer not found in chroot!"
fi

# 3. Configure Boot Experience & Virtual Machine Reliability
echo "Configuring GRUB, Plymouth, and Virtual Display Drivers..."
mkdir -p /etc/default/grub.d /boot/grub /usr/share/backgrounds

# Ensure wallpaper is present for GRUB early display
if [ -f "/opt/snowos-installer/assets/snowos-wallpaper.png" ]; then
    cp -f "/opt/snowos-installer/assets/snowos-wallpaper.png" /boot/grub/snowos-wallpaper.png
    cp -f "/opt/snowos-installer/assets/snowos-wallpaper.png" /usr/share/backgrounds/snowos-wallpaper.png
elif [ -f "/usr/share/backgrounds/snowos-wallpaper.png" ]; then
    cp -f "/usr/share/backgrounds/snowos-wallpaper.png" /boot/grub/snowos-wallpaper.png
fi
chmod 0644 /boot/grub/snowos-wallpaper.png 2>/dev/null || true

cat > /etc/default/grub.d/50-snowos.cfg << 'EOF'
# SnowOS Aurora Visual & Boot Reliability Configuration
GRUB_DISTRIBUTOR="SnowOS Aurora"
GRUB_TIMEOUT=5
GRUB_TIMEOUT_STYLE=menu
GRUB_GFXMODE="auto,1920x1080,1366x768,1024x768,800x600,auto"
GRUB_GFXPAYLOAD_LINUX="auto"
GRUB_TERMINAL_OUTPUT="gfxterm"
GRUB_DISABLE_RECOVERY=false
GRUB_DISABLE_OS_PROBER=false
GRUB_BACKGROUND="/boot/grub/snowos-wallpaper.png"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash plymouth.ignore-serial-consoles"
EOF

if [ -f /etc/default/grub ]; then
    sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="SnowOS Aurora"/g' /etc/default/grub 2>/dev/null || true
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash plymouth.ignore-serial-consoles"/g' /etc/default/grub 2>/dev/null || true
    sed -i 's/^GRUB_GFXPAYLOAD_LINUX=.*/GRUB_GFXPAYLOAD_LINUX=auto/g' /etc/default/grub 2>/dev/null || true
    sed -i 's/^GRUB_TERMINAL_OUTPUT=.*/GRUB_TERMINAL_OUTPUT="gfxterm"/g' /etc/default/grub 2>/dev/null || true
    sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=menu/g' /etc/default/grub 2>/dev/null || true
    sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/g' /etc/default/grub 2>/dev/null || true
fi

# Add VM video drivers for early initramfs KMS
if [ -f /etc/initramfs-tools/modules ]; then
    for mod in vboxvideo vmwgfx virtio_gpu qxl bochs_drm; do
        if ! grep -qx "$mod" /etc/initramfs-tools/modules; then
            echo "$mod" >> /etc/initramfs-tools/modules
        fi
    done
fi

if command -v update-initramfs >/dev/null 2>&1; then
    update-initramfs -u 2>/dev/null || true
fi
if command -v update-grub >/dev/null 2>&1; then
    update-grub 2>/dev/null || true
fi

# 4. Clean up Ubuntu references
echo "Purging legacy Ubuntu wallpapers and transitional packages..."
apt-get purge -y ubuntu-wallpapers* ubuntu-mono ubuntu-advantage-tools 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true
apt-get clean 2>/dev/null || true

echo "SnowOS Chroot Hook Complete."
