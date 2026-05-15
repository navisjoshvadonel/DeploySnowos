#!/bin/bash
set -e

echo "--- Starting Root-level Visual Applications ---"

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
cp /home/develop/snowos/assets/snowos-wallpaper.png /usr/share/backgrounds/snowos-wallpaper.png

# 3. Apply identity files
echo "[*] Copying identity files..."
dpkg-divert --remove --rename /etc/os-release || true
dpkg-divert --remove --rename /etc/lsb-release || true
rm -f /etc/os-release.ubuntu /etc/os-release.ubuntu-default /etc/lsb-release.ubuntu /etc/lsb-release.ubuntu-default
cp /home/develop/snowos/identity/os-release /etc/os-release
cp /home/develop/snowos/identity/lsb-release /etc/lsb-release

# 4. Copy logo
echo "[*] Copying logo..."
cp /home/develop/snowos/assets/logo.png /usr/share/pixmaps/snowos-logo.png
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

