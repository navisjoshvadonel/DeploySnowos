#!/bin/bash

# SnowOS UI Installation Script
# This script applies the "Frozen Minimal" UI identity system.

# set -e # Removed to allow continuation on dconf errors

# Colors for output
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================"
echo -e "   SnowOS Frozen Minimal UI Installer   "
echo -e "========================================${NC}"

# 1. Paths
SNOWOS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLANK_THEME_DIR="$HOME/.local/share/plank/themes/snowos-frozen"
PLANK_CONFIG_DIR="$HOME/.config/plank/dock1"
AUTOSTART_DIR="$HOME/.config/autostart"
ICON_DEST="$HOME/.local/share/icons/SnowOS-Frozen"

# 2. Plank Theme Installation
echo -e "${CYAN}[1/6] Installing Plank Theme...${NC}"
mkdir -p "$PLANK_THEME_DIR"
cp "$SNOWOS_ROOT/ui/plank/snowos-frozen/dock.theme" "$PLANK_THEME_DIR/"
echo -e "      - Theme copied to $PLANK_THEME_DIR"

# 3. Plank Configuration
echo -e "${CYAN}[2/6] Applying Plank Settings...${NC}"
if command -v dconf >/dev/null; then
    dconf load / < "$SNOWOS_ROOT/ui/plank/config/settings" || echo -e "      - Note: Some Plank settings were non-writable."
    echo -e "      - Plank settings application attempted"
else
    echo -e "      - Warning: dconf not found. Skipping Plank settings."
fi

# 4. System UI Overrides (dconf)
echo -e "${CYAN}[3/6] Applying System UI Settings...${NC}"
if command -v dconf >/dev/null; then
    dconf load / < "$SNOWOS_ROOT/ui/dconf/00-snowos-ui" || echo -e "      - Note: Some system settings were non-writable."
    echo -e "      - GNOME/System settings application attempted"
else
    echo -e "      - Warning: dconf not found. Skipping system settings."
fi

# 5. Autostart Integration
echo -e "${CYAN}[4/6] Enabling Plank Autostart...${NC}"
mkdir -p "$AUTOSTART_DIR"
cp "$SNOWOS_ROOT/ui/plank/autostart/plank.desktop" "$AUTOSTART_DIR/"
echo -e "      - Autostart entry created at $AUTOSTART_DIR/plank.desktop"

# 6. Icon Theme Installation
echo -e "${CYAN}[5/6] Installing Frozen Icon Theme...${NC}"
mkdir -p "$ICON_DEST"
cp -r "$SNOWOS_ROOT/ui/icons/snowos-frozen/"* "$ICON_DEST/"
echo -e "      - Icons installed to $ICON_DEST"

# 7. Finalizing
echo -e "${CYAN}[6/6] Refreshing UI Components...${NC}"
# Kill existing plank if running, it will restart if autostarted or manual
pkill plank || true
nohup plank >/dev/null 2>&1 &

echo -e "${GREEN}========================================"
echo -e "   SnowOS UI Successfully Installed!   "
echo -e "========================================${NC}"
echo -e "Please log out and log back in for full GNOME shell changes."
