#!/bin/bash

set -e

echo "SnowOS Visual Prep"
echo "------------------"

sudo apt update
sudo apt install -y gnome-shell-extension-dash-to-dock gnome-tweaks

echo "Visual tooling installed."
echo "Use SnowOS visual scripts to apply your dock, theme, and icon branding."
echo "Crash reporting and system logs were left untouched on purpose."
