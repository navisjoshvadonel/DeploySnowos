#!/bin/bash

EXT_DIR="$HOME/.local/share/gnome-shell/extensions/snowos-ui-engine@snowos.org"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../ui_engine/theme_engine/ui/extension" 2>/dev/null && pwd)"

if [ -z "$SRC_DIR" ] || [ ! -d "$SRC_DIR" ]; then
  echo "SnowOS UI Engine source not found."
  exit 1
fi

echo "Installing SnowOS UI Engine..."

mkdir -p "$EXT_DIR"
cp "$SRC_DIR"/* "$EXT_DIR/"

echo "Enabling extension..."
gnome-extensions enable snowos-ui-engine@snowos.org

echo "SnowOS UI Engine deployed."
echo "Restart GNOME Shell or log out and back in to see changes."
