#!/bin/bash
# SnowOS Aurora Branding Application Script
# This script safely replaces Ubuntu branding with SnowOS Aurora identity and visual assets.

set -e

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./apply_branding.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDENTITY_DIR="$SCRIPT_DIR/identity"
ASSETS_DIR="$SCRIPT_DIR/assets"
OS_RELEASE_SRC="$IDENTITY_DIR/os-release"
LSB_RELEASE_SRC="$IDENTITY_DIR/lsb-release"
LOGO_SRC="$ASSETS_DIR/logo.png"

WALLPAPER_SRC="$ASSETS_DIR/snowos-wallpaper.png"

# Check if source files exist
if [ ! -f "$OS_RELEASE_SRC" ]; then
    echo "[!] Error: $OS_RELEASE_SRC not found."
    exit 1
fi

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

# 2. Visual Branding (Logo, Icons & Wallpaper)
echo "[*] Deploying SnowOS Aurora logo..."
cp "$LOGO_SRC" /usr/share/pixmaps/snowos-logo.png
# Provide a system-wide symlink for the logo
ln -sf /usr/share/pixmaps/snowos-logo.png /usr/share/pixmaps/system-logo.png

echo "[*] Deploying SnowOS Wallpaper..."
mkdir -p /usr/share/backgrounds
if [ -f "$WALLPAPER_SRC" ]; then
    cp "$WALLPAPER_SRC" /usr/share/backgrounds/snowos-wallpaper.png
fi

echo "[*] Setting system defaults via glib schemas..."
cat > /usr/share/glib-2.0/schemas/99_snowos.gschema.override <<EOF
[org.gnome.desktop.background]
picture-uri='file:///usr/share/backgrounds/snowos-wallpaper.png'
picture-uri-dark='file:///usr/share/backgrounds/snowos-wallpaper.png'

[org.gnome.desktop.interface]
icon-theme='SnowOS'
gtk-theme='WhiteSur-Dark'
EOF
glib-compile-schemas /usr/share/glib-2.0/schemas/ || true

echo "[*] Configuring SnowOS Icon Theme alias..."
mkdir -p /usr/share/icons/SnowOS
cat > /usr/share/icons/SnowOS/index.theme <<EOF
[Icon Theme]
Name=SnowOS
Inherits=Papirus,WhiteSur,Adwaita,hicolor
Comment=SnowOS custom icon theme alias
Directories=
EOF

# 3. Update GRUB configuration
echo "[*] Updating GRUB distributor branding and background..."
if grep -q "GRUB_DISTRIBUTOR" /etc/default/grub; then
    sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="SnowOS Aurora"/' /etc/default/grub
else
    echo 'GRUB_DISTRIBUTOR="SnowOS Aurora"' >> /etc/default/grub
fi

if grep -q "GRUB_BACKGROUND" /etc/default/grub; then
    sed -i 's|^GRUB_BACKGROUND=.*|GRUB_BACKGROUND="/usr/share/backgrounds/snowos-wallpaper.png"|' /etc/default/grub
else
    echo 'GRUB_BACKGROUND="/usr/share/backgrounds/snowos-wallpaper.png"' >> /etc/default/grub
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
