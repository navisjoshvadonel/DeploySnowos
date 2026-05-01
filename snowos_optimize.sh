#!/bin/bash

# SnowOS Optimization Script
# Goal: Disable Ubuntu crash reports & Prep UI for macOS aesthetic

echo "❄️ Starting SnowOS System Cleanup..."

# 1. Disable Apport (The 'Internal Error' Pop-up)
echo "-----------------------------------------------"
echo "🔧 Disabling Ubuntu Error Reporting (Apport)..."
sudo sed -i 's/enabled=1/enabled=0/g' /etc/default/apport
sudo systemctl stop apport.service
sudo systemctl disable apport.service
echo "✅ Apport disabled."

# 2. Clear Existing Crash Logs
echo "-----------------------------------------------"
echo "🧹 Clearing old crash reports..."
sudo rm -rf /var/crash/*
echo "✅ Crash logs cleared."

# 3. Install Dash to Dock & Tweaks
echo "-----------------------------------------------"
echo "📦 Installing UI Customization tools..."
sudo apt update && sudo apt install -y gnome-shell-extension-dash-to-dock gnome-tweaks
echo "✅ Tools installed."

# 4. Final Notification
echo "-----------------------------------------------"
echo "✨ System optimized for SnowOS."
echo "🚀 Next steps: Use GNOME Tweaks to apply your macOS icon theme."
echo "🔄 Please log out and back in for all changes to take effect."
