#!/bin/bash
# install_cli.sh
# Installs the snowos CLI globally

CLI_SCRIPT="/home/develop/snowos/system/cli.py"
TARGET="/usr/local/bin/snowos"

echo "Installing SnowOS CLI..."
chmod +x "$CLI_SCRIPT"

if [ -L "$TARGET" ] || [ -f "$TARGET" ]; then
    sudo rm -f "$TARGET"
fi

sudo ln -s "$CLI_SCRIPT" "$TARGET"

if [ -x "$TARGET" ]; then
    echo "SnowOS CLI installed successfully at $TARGET"
    echo "Test by running: snowos --help"
else
    echo "Failed to install SnowOS CLI."
    exit 1
fi
