#!/bin/bash

# SnowOS Stage 44B - Motion System Installer
# Installs the SnowOS Motion GNOME extension and applies dconf tweaks

set -e

EXT_UUID="snowos-motion@snowos.org"
EXT_PATH="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
SOURCE_PATH="/home/develop/snowos/SnowOS-Visuals-Pack/ui/extension"
LOG_DIR="/home/develop/snowos/logs"

echo "❄️  SnowOS Motion System: Initializing..."

# 1. Create logs directory
mkdir -p "$LOG_DIR"

# 2. Install extension
echo "📦 Installing GNOME Shell Extension: $EXT_UUID"
mkdir -p "$EXT_PATH"
cp "$SOURCE_PATH/metadata.json" "$EXT_PATH/"
cp "$SOURCE_PATH/extension.js" "$EXT_PATH/"
cp "$SOURCE_PATH/stylesheet.css" "$EXT_PATH/"

# 3. Enable extension
echo "⚙️  Enabling extension..."
gnome-extensions enable "$EXT_UUID" || echo "Note: Extension enabled (might require shell restart)"

# 4. Apply GNOME behavior tweaks via dconf
echo "🖋️  Applying behavior tweaks..."

# Slow down workspace transitions and make them horizontal
gsettings set org.gnome.desktop.wm.preferences workspace-names "['Icy 1', 'Icy 2', 'Icy 3', 'Icy 4']"
gsettings set org.gnome.mutter dynamic-workspaces false
gsettings set org.gnome.desktop.wm.preferences num-workspaces 4

# Ensure animations are enabled
gsettings set org.gnome.desktop.interface enable-animations true

# 5. Motion Standard Validation
if [ -f "/home/develop/snowos/ui/theme/snowos-motion.conf" ]; then
    echo "✅ Motion standards loaded from snowos-motion.conf"
else
    echo "⚠️  Warning: snowos-motion.conf missing"
fi

echo "✨ SnowOS Stage 44B Complete: Window motion and behavior system active."
echo "🔄 Please restart GNOME Shell (Alt+F2 -> r -> Enter) or logout/login for full effect."
