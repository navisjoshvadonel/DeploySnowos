#!/bin/bash

# /home/develop/snowos/scripts/uninstall-visual-pack.sh
# SnowOS Visual Pack Uninstaller
# Reverts system to default Ubuntu (Yaru) theme

set -e

# --- SAFETY CHECKS ---
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (use sudo)."
   exit 1
fi

# Determine the actual user who invoked sudo
ACTUAL_USER=${SUDO_USER:-$USER}

echo "Starting restoration of default GNOME environment..."

# 1. RESTORE DEFAULT THEMES
echo "Restoring default Ubuntu GTK theme (Yaru)..."
sudo -u "$ACTUAL_USER" gsettings set org.gnome.desktop.interface gtk-theme 'Yaru'
sudo -u "$ACTUAL_USER" gsettings set org.gnome.desktop.wm.preferences theme 'Yaru'

echo "Restoring default icons..."
sudo -u "$ACTUAL_USER" gsettings set org.gnome.desktop.interface icon-theme 'Yaru'

# 2. RESET GNOME SETTINGS
echo "Resetting GNOME settings to defaults..."
# This command resets ALL settings under /org/gnome/ as requested
sudo -u "$ACTUAL_USER" dconf reset -f /org/gnome/

# 3. REMOVE SNOWOS ASSETS
echo "Removing SnowOS icon/theme folders..."
rm -rf /usr/share/icons/SnowOS
rm -rf /usr/share/themes/SnowOS

# 4. RESTORE LOGIN BACKGROUND
echo "Restoring default login background..."
rm -f /usr/share/backgrounds/snowos-login.png
rm -f /usr/share/icons/snowflake.png

echo "SnowOS UI uninstallation complete"
