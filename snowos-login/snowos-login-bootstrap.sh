#!/bin/bash
# SnowOS Login Bootstrap Script
# Launches the standalone Digital Frost UI via xinit

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
UI_LAUNCHER="$SCRIPT_DIR/login_app.py"

echo "❄️  SnowOS Login Bootstrap Initializing..."

# Wait a moment for graphics hardware
sleep 2

# Check if another Display Manager is active (gdm3, sddm, lightdm)
if systemctl is-active --quiet gdm.service || systemctl is-active --quiet sddm.service || systemctl is-active --quiet lightdm.service; then
    echo "Display Manager is active. Aborting Digital Frost Greeter."
    exit 0
fi

# Fallback: start our WebKit UI via xinit
echo "No Display Manager active. Launching Digital Frost Greeter via xinit..."

if command -v xinit > /dev/null; then
    export DISPLAY=:0
    # Launch UI without a window manager, pure fullscreen
    # using vt7 explicitly to separate from tty1 logging
    xinit /usr/bin/python3 "$UI_LAUNCHER" -- :0 vt7
else
    echo "CRITICAL: xinit not found. Falling back to terminal mode."
    exit 1
fi
