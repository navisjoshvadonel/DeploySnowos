#!/bin/bash
# SnowOS UI Engine Installer

EXT_DIR="$HOME/.local/share/gnome-shell/extensions/snowos-ui-engine@snowos.org"
SRC_DIR="/home/develop/snowos/core/ui-engine/extension"

echo "❄️ Installing SnowOS UI Engine..."

mkdir -p "$EXT_DIR"
cp "$SRC_DIR"/* "$EXT_DIR/"

echo "❄️ Enabling extension..."
gnome-extensions enable snowos-ui-engine@snowos.org

echo "❄️ SnowOS UI Engine Stage 1 & 2 prototype deployed."
echo "Note: You may need to restart GNOME Shell (Alt+F2 -> r -> Enter) or log out/in to see changes."
