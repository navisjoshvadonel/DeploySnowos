#!/bin/bash
# SnowOS Login Theme Applicator
# This script compiles the Cyber-Glacier GDM theme and applies it to the system.

# Correct paths
THEME_DIR="/home/develop/snowos/gdm-theme-build-v2/theme"
XML_FILE="snowos.gresource.xml"
RESOURCE_FILE="snowos.gresource"
SYSTEM_RESOURCE="/usr/share/gnome-shell/theme/snowos.gresource"

echo "❄️ Compiling SnowOS Login Resources..."
if [ ! -f "$THEME_DIR/$XML_FILE" ]; then
    echo "❌ Error: $XML_FILE not found in $THEME_DIR"
    exit 1
fi

cd "$THEME_DIR"
glib-compile-resources "$XML_FILE" --target="$RESOURCE_FILE"

if [ $? -ne 0 ]; then
    echo "❌ Error: Compilation failed."
    exit 1
fi

echo "❄️ Applying Theme to System..."
sudo mkdir -p /usr/share/gnome-shell/theme/

# Copy the new resource
sudo cp "$THEME_DIR/$RESOURCE_FILE" "$SYSTEM_RESOURCE"

# Set as default using update-alternatives
echo "❄️ Updating System Theme Alternatives..."
sudo update-alternatives --install /usr/share/gnome-shell/gnome-shell-theme.gresource \
    gnome-shell-theme.gresource "$SYSTEM_RESOURCE" 50

sudo update-alternatives --set gnome-shell-theme.gresource "$SYSTEM_RESOURCE"

echo "❄️ SnowOS Login Page applied successfully!"
echo "------------------------------------------------"
echo "To see the changes, you MUST restart GDM."
echo "WARNING: This will close all your open windows and log you out."
echo "Run this command to restart now:"
echo "sudo systemctl restart gdm"
