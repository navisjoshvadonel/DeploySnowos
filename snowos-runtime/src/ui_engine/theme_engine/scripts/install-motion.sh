#!/bin/bash

set -e

EXT_UUID="snowos-motion@snowos.org"
EXT_PATH="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_PATH="$ENGINE_ROOT/ui/extension"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/snowos"
MOTION_CONF="$ENGINE_ROOT/ui/theme/snowos-motion.conf"

echo "SnowOS Motion System: Initializing..."
mkdir -p "$LOG_DIR"

echo "Installing GNOME Shell Extension: $EXT_UUID"
mkdir -p "$EXT_PATH"
cp "$SOURCE_PATH/metadata.json" "$EXT_PATH/"
cp "$SOURCE_PATH/extension.js" "$EXT_PATH/"
cp "$SOURCE_PATH/stylesheet.css" "$EXT_PATH/"

echo "Enabling extension..."
gnome-extensions enable "$EXT_UUID" || echo "Note: extension may require a shell restart"

echo "Applying behavior tweaks..."
gsettings set org.gnome.desktop.wm.preferences workspace-names "['Icy 1', 'Icy 2', 'Icy 3', 'Icy 4']"
gsettings set org.gnome.mutter dynamic-workspaces false
gsettings set org.gnome.desktop.wm.preferences num-workspaces 4
gsettings set org.gnome.desktop.interface enable-animations true

if [ -f "$MOTION_CONF" ]; then
    echo "Motion standards loaded from snowos-motion.conf"
else
    echo "Warning: snowos-motion.conf missing"
fi

echo "SnowOS Motion System active."
echo "Restart GNOME Shell or log out and back in for full effect."
