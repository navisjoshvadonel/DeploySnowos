#!/bin/bash
set -e

echo "=========================================="
echo "❄️  Installing SnowOS Runtime Overlay ❄️"
echo "=========================================="

# 1. Environment Setup
echo "[+] Checking environment..."
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./install.sh)"
  exit 1
fi

echo "[+] Creating dedicated service users..."
id -u snowos-sys &>/dev/null || useradd -r -s /bin/false snowos-sys
id -u snowos-ai &>/dev/null || useradd -r -s /bin/false snowos-ai

echo "[+] Setting up directories..."
mkdir -p /etc/snowos
mkdir -p /opt/snowos

# 2. Deploying Codebase
echo "[+] Deploying codebase to /opt/snowos..."
cp -R ./snowos-runtime/src/* /opt/snowos/
chown -R root:root /opt/snowos

# Setup specific permissions for sockets and DBs
mkdir -p /tmp/snowos_sockets
chown snowos-sys:snowos-sys /tmp/snowos_sockets
chmod 777 /tmp/snowos_sockets

# 3. Configurations
echo "[+] Copying configurations..."
cp /opt/snowos/system_services/permission_broker/capabilities.json /etc/snowos/
chown snowos-sys:snowos-sys /etc/snowos/capabilities.json

# 4. Service Registration
echo "[+] Registering systemd services..."
cp ./snowos-runtime/services/*.service /etc/systemd/system/
systemctl daemon-reload

echo "[+] Enabling services..."
systemctl enable snowos-broker.service
systemctl enable snowos-sentinel.service
systemctl enable snowos-aicore.service
systemctl enable snowos-optimizer.service
systemctl enable snowos-control.service

# We don't start them immediately in the script to allow manual verification,
# or we can start them.
echo "[+] Starting core services..."
systemctl start snowos-broker.service || echo "Broker start deferred"
systemctl start snowos-sentinel.service || echo "Sentinel start deferred"

echo "=========================================="
echo "✅ SnowOS Runtime Installation Complete."
echo "   Run validation/check_health.py to verify."
echo "=========================================="
