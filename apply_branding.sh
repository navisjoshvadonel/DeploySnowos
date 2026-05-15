#!/bin/bash
# SnowOS Aurora Branding Application Script
# This script safely replaces Ubuntu branding with SnowOS Aurora identity and visual assets.

set -e

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./apply_branding.sh)"
  exit 1
fi

IDENTITY_DIR="/home/develop/snowos/identity"
ASSETS_DIR="/home/develop/snowos/assets"
OS_RELEASE_SRC="$IDENTITY_DIR/os-release"
LSB_RELEASE_SRC="$IDENTITY_DIR/lsb-release"
LOGO_SRC="$ASSETS_DIR/logo.png"

echo "--- Starting SnowOS Aurora Branding Transition ---"

# 1. Identity Files
if ! dpkg-divert --list /etc/os-release | grep -q "diverted by snowos"; then
    echo "[*] Diverting /etc/os-release..."
    dpkg-divert --add --rename --divert /etc/os-release.ubuntu /etc/os-release
fi

if ! dpkg-divert --list /etc/lsb-release | grep -q "diverted by snowos"; then
    echo "[*] Diverting /etc/lsb-release..."
    dpkg-divert --add --rename --divert /etc/lsb-release.ubuntu /etc/lsb-release
fi

echo "[*] Deploying identity files..."
cp "$OS_RELEASE_SRC" /etc/os-release
cp "$LSB_RELEASE_SRC" /etc/lsb-release

# 2. Visual Branding (Logo & Icons)
echo "[*] Deploying SnowOS Aurora logo..."
cp "$LOGO_SRC" /usr/share/pixmaps/snowos-logo.png
# Provide a system-wide symlink for the logo
ln -sf /usr/share/pixmaps/snowos-logo.png /usr/share/pixmaps/system-logo.png

echo "[*] Setting system icon theme..."
# Set global icon theme for all users (if gsettings is available)
if command -v gsettings >/dev/null; then
    # We apply this to the current user, but ideally it should be in the default profile
    # For a platform-level change, we modify the default settings
    echo "[*] Configuring GNOME icon theme..."
    gsettings set org.gnome.desktop.interface icon-theme "SnowOS" || true
    gsettings set org.gnome.desktop.interface gtk-theme "WhiteSur-Dark" || true
fi

# 3. Update GRUB configuration
echo "[*] Updating GRUB distributor branding..."
if grep -q "GRUB_DISTRIBUTOR" /etc/default/grub; then
    sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="SnowOS Aurora"/' /etc/default/grub
else
    echo 'GRUB_DISTRIBUTOR="SnowOS Aurora"' >> /etc/default/grub
fi

echo "[*] Refreshing GRUB entries..."
update-grub

# 4. Update terminal login banners
echo "[*] Updating login banners..."
cat > /etc/issue <<EOF
SnowOS Aurora 24.04 \n \l

EOF

cat > /etc/issue.net <<EOF
SnowOS Aurora 24.04
EOF

echo "[*] Branding applied successfully."
echo "--- Verification ---"
echo "OS Name: $(grep PRETTY_NAME /etc/os-release | cut -d= -f2)"
echo "Icons: SnowOS"
echo "Logo: /usr/share/pixmaps/snowos-logo.png"
echo "-----------------------------------------------"
echo "Transition complete. Please reboot to see all changes."
