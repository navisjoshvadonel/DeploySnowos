#!/bin/bash

# /home/develop/snowos/scripts/install-visual-pack.sh
# SnowOS Visual Pack Installer
# Expertly crafted for SnowOS (Ubuntu-based GNOME)

set -e

# --- CONFIGURATION ---
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
ASSETS_DIR="$PROJECT_ROOT/assets"
BACKUP_DIR="$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S)"

# --- SAFETY CHECKS ---
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (use sudo)."
   exit 1
fi

# Determine the actual user who invoked sudo
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo "~$ACTUAL_USER")

# Check if assets exist
if [ ! -d "$ASSETS_DIR" ]; then
    echo "Error: Assets directory not found at $ASSETS_DIR"
    exit 1
fi

# --- HELPER FUNCTIONS ---
# This ensures gsettings commands reach the user's desktop session correctly
run_user_cmd() {
    local user_id=$(id -u "$ACTUAL_USER")
    local dbus_address="unix:path=/run/user/$user_id/bus"
    
    if [ -S "/run/user/$user_id/bus" ]; then
        sudo -u "$ACTUAL_USER" DBUS_SESSION_BUS_ADDRESS="$dbus_address" "$@"
    else
        sudo -u "$ACTUAL_USER" "$@"
    fi
}

echo "Initializing SnowOS Visual Transformation..."

# 1. BACKUP CURRENT SETTINGS
echo "Backing up current theme settings to $BACKUP_DIR..."
mkdir -p "$BACKUP_DIR"

# Save current settings for recovery
run_user_cmd gsettings get org.gnome.desktop.interface gtk-theme > "$BACKUP_DIR/gtk_theme.bak" 2>/dev/null || true
run_user_cmd gsettings get org.gnome.desktop.interface icon-theme > "$BACKUP_DIR/icon_theme.bak" 2>/dev/null || true

# 2. APPLY GTK THEME
echo "Applying SnowOS UI theme..."
if [ -d "$ASSETS_DIR/gtk-theme" ]; then
    mkdir -p /usr/share/themes/SnowOS
    cp -r "$ASSETS_DIR/gtk-theme/." /usr/share/themes/SnowOS/
    
    run_user_cmd gsettings set org.gnome.desktop.interface gtk-theme 'SnowOS'
    run_user_cmd gsettings set org.gnome.desktop.wm.preferences theme 'SnowOS'
else
    echo "Warning: $ASSETS_DIR/gtk-theme not found. Skipping GTK theme application."
fi

# 3. INSTALL ICONS & CURSORS
echo "Deploying custom SnowOS Crystal icons with Deep Theming..."
mkdir -p "$ASSETS_DIR/icons/apps/scalable/"

# Define mappings for modern GNOME App IDs
# Firefox (Snap fix)
cp "$ASSETS_DIR/icons/apps/scalable/firefox.png" "$ASSETS_DIR/icons/apps/scalable/org.mozilla.firefox.png"

# Terminal
cp "$ASSETS_DIR/icons/apps/scalable/org.gnome.Terminal.png" "$ASSETS_DIR/icons/apps/scalable/utilities-terminal.png"

# Files / Nautilus
cp "$ASSETS_DIR/icons/apps/scalable/org.gnome.Nautilus.png" "$ASSETS_DIR/icons/apps/scalable/system-file-manager.png"

# Settings
cp "$ASSETS_DIR/icons/apps/scalable/org.gnome.Settings.png" "$ASSETS_DIR/icons/apps/scalable/preferences-system.png"

echo "Installing icon and cursor packs..."
mkdir -p /usr/share/icons/SnowOS
cp -r "$ASSETS_DIR/icons/." /usr/share/icons/SnowOS/
run_user_cmd gsettings set org.gnome.desktop.interface icon-theme 'SnowOS'

# --- DEEP THEMING: LIBERATE SNAP ICONS ---
echo "Liberating Snap application icons..."
LOCAL_APPS="$USER_HOME/.local/share/applications"
mkdir -p "$LOCAL_APPS"

# Fix Firefox Snap Icon
if [ -f "/var/lib/snapd/desktop/applications/firefox_firefox.desktop" ]; then
    cp "/var/lib/snapd/desktop/applications/firefox_firefox.desktop" "$LOCAL_APPS/firefox.desktop"
    sed -i 's|^Icon=.*|Icon=firefox|g' "$LOCAL_APPS/firefox.desktop"
    chown "$ACTUAL_USER":"$ACTUAL_USER" "$LOCAL_APPS/firefox.desktop"
fi

# Refresh Icon Cache
gtk-update-icon-cache -f /usr/share/icons/SnowOS/ 2>/dev/null || true
touch /usr/share/icons/SnowOS

# Set a clean white cursor theme as the SnowOS base
if [ -d "/usr/share/icons/DMZ-White" ]; then
    echo "Applying SnowOS Crystal cursor..."
    run_user_cmd gsettings set org.gnome.desktop.interface cursor-theme 'DMZ-White'
fi

# 4. CONFIGURE LOGIN SCREEN (GDM)
echo "Configuring login screen..."
mkdir -p /usr/share/backgrounds
if [ -f "$ASSETS_DIR/loginwall.png" ]; then
    cp "$ASSETS_DIR/loginwall.png" /usr/share/backgrounds/snowos-login.png
    # Set as lockscreen background for the user as well
    run_user_cmd gsettings set org.gnome.desktop.screensaver picture-uri "file:///usr/share/backgrounds/snowos-login.png"
fi

if [ -f "$ASSETS_DIR/snowflake.png" ]; then
    cp "$ASSETS_DIR/snowflake.png" /usr/share/icons/snowflake.png
fi

# 5. DOCK + SHELL APPEARANCE
echo "Configuring shell and dock appearance..."

# Install SnowOS Motion Extension
EXTENSION_UUID="snowos-motion@snowos.org"
EXTENSION_SRC="$PROJECT_ROOT/SnowOS-Visuals-Pack/ui/extension"
EXTENSION_DEST="$USER_HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"

if [ -d "$EXTENSION_SRC" ]; then
    echo "Installing SnowOS Motion extension..."
    sudo -u "$ACTUAL_USER" mkdir -p "$EXTENSION_DEST"
    sudo -u "$ACTUAL_USER" cp -r "$EXTENSION_SRC/." "$EXTENSION_DEST/"
    run_user_cmd gnome-extensions enable "$EXTENSION_UUID" 2>/dev/null || true
fi

# Enable user-theme extension if it exists
if run_user_cmd gnome-extensions list | grep -q "user-theme"; then
    run_user_cmd gnome-extensions enable user-theme@gnome-shell-extensions.gcampax.github.com 2>/dev/null || true
    run_user_cmd gsettings set org.gnome.shell.extensions.user-theme name 'SnowOS'
fi

# Dash-to-dock configuration
if run_user_cmd gnome-extensions list | grep -q "dash-to-dock"; then
    echo "Modernizing dash-to-dock..."
    run_user_cmd gnome-extensions enable dash-to-dock@micxgx.gmail.com 2>/dev/null || true
    
    # SYSTEM-WIDE OVERRIDE (to bypass locks)
    cat <<EOF > /etc/dconf/db/local.d/00-snowos-dock
[org/gnome/shell/extensions/dash-to-dock]
dock-position='BOTTOM'
extend-height=false
dash-max-icon-size=44
transparency-mode='FIXED'
background-opacity=0.2
custom-theme-shrink=true
autohide=false
EOF
    
    # Update the system dconf database
    dconf update
    echo "System-wide dock settings applied and locked keys bypassed."
fi

# Plank Dock Theme (if available)
PLANK_THEME_SRC="$PROJECT_ROOT/SnowOS-Visuals-Pack/ui/plank/themes/SnowOS"
PLANK_DEST="$USER_HOME/.local/share/plank/themes/SnowOS"

if [ -d "$PLANK_THEME_SRC" ]; then
    echo "Installing Plank dock theme..."
    sudo -u "$ACTUAL_USER" mkdir -p "$PLANK_DEST"
    sudo -u "$ACTUAL_USER" cp -r "$PLANK_THEME_SRC/." "$PLANK_DEST/"
fi

echo "SnowOS UI installation complete"
