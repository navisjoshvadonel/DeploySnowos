#!/bin/bash
set -e

echo "--- Starting Root-level Visual Applications ---"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Unique Icon Set Injection
echo "[*] Creating icon theme..."
mkdir -p /usr/share/icons/snowos-frozen
cat > /usr/share/icons/snowos-frozen/index.theme <<EOF
[Icon Theme]
Name=SnowOS-Frozen
Inherits=Papirus-Dark,WhiteSur,Adwaita,hicolor
Comment=SnowOS Frozen custom icon theme
Directories=
EOF

# Copy snowflake if we want, but it's inherited so maybe not strictly needed
# Just rebuilding cache
echo "[*] Rebuilding icon cache..."
gtk-update-icon-cache /usr/share/icons/snowos-frozen -f || true

# 2. Static Snow Wallpaper
echo "[*] Copying wallpaper..."
mkdir -p /usr/share/backgrounds
cp "$SCRIPT_DIR/assets/snowos-wallpaper.png" /usr/share/backgrounds/snowos-wallpaper.png

# 3. Apply identity files
echo "[*] Copying identity files..."
for target in /etc/os-release /etc/lsb-release; do
    echo "[!] Fixing conflicting diversion for $target..."
    dpkg-divert --remove --rename "$target" 2>/dev/null || true
    rm -f "$target.ubuntu" "$target.ubuntu-default"
done

echo "[*] Restoring base system files to clean state..."
apt-get install --reinstall -y base-files >/dev/null 2>&1

if ! dpkg-divert --list /etc/os-release | grep -q "diverted by snowos"; then
    dpkg-divert --add --rename --divert /etc/os-release.ubuntu /etc/os-release
fi

if ! dpkg-divert --list /etc/lsb-release | grep -q "diverted by snowos"; then
    dpkg-divert --add --rename --divert /etc/lsb-release.ubuntu /etc/lsb-release
fi

cp "$SCRIPT_DIR/identity/os-release" /etc/os-release
cp "$SCRIPT_DIR/identity/lsb-release" /etc/lsb-release

# 4. Copy logo
echo "[*] Copying logo..."
cp "$SCRIPT_DIR/assets/logo.png" /usr/share/pixmaps/snowos-logo.png

ln -sf /usr/share/pixmaps/snowos-logo.png /usr/share/pixmaps/system-logo.png

# 5. Update GRUB
echo "[*] Updating GRUB..."
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
update-grub

# 6. Replace orange colors with blue in GDM theme
echo "[*] Injecting blue palette into Yaru GDM theme..."
# Backup first
if [ ! -f /usr/share/gnome-shell/theme/Yaru/gnome-shell.css.bak ]; then
    cp /usr/share/gnome-shell/theme/Yaru/gnome-shell.css /usr/share/gnome-shell/theme/Yaru/gnome-shell.css.bak
fi
sed -i 's/#E95420/#007bff/gi' /usr/share/gnome-shell/theme/Yaru/gnome-shell.css
sed -i 's/#e95420/#007bff/gi' /usr/share/gnome-shell/theme/Yaru/gnome-shell.css

# 7. Update dconf to force system-wide UI changes
echo "[*] Updating dconf profile for UI settings..."
mkdir -p /etc/dconf/db/local.d
cat > /etc/dconf/db/local.d/99-snowos-branding <<EOF
[org/gnome/desktop/interface]
icon-theme='snowos-frozen'
accent-color='blue'

[org/gnome/desktop/background]
picture-uri='file:///usr/share/backgrounds/snowos-wallpaper.png'
picture-uri-dark='file:///usr/share/backgrounds/snowos-wallpaper.png'
picture-options='zoom'

[org/gnome/shell/extensions/dash-to-dock]
transparency-mode='FIXED'
background-opacity=0.0
EOF

dconf update

echo "--- Root-level applications completed ---"

