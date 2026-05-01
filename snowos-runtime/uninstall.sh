#!/bin/bash
set -e

echo "=========================================="
echo "🔥  Uninstalling SnowOS Runtime Overlay 🔥"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./uninstall.sh)"
  exit 1
fi

echo "[-] Stopping services..."
systemctl stop snowos-broker.service || true
systemctl stop snowos-sentinel.service || true
systemctl stop snowos-aicore.service || true
systemctl stop snowos-optimizer.service || true
systemctl stop snowos-control.service || true

echo "[-] Disabling services..."
systemctl disable snowos-broker.service || true
systemctl disable snowos-sentinel.service || true
systemctl disable snowos-aicore.service || true
systemctl disable snowos-optimizer.service || true
systemctl disable snowos-control.service || true

echo "[-] Removing systemd files..."
rm -f /etc/systemd/system/snowos-*.service
systemctl daemon-reload

echo "[-] Removing code and configs..."
rm -rf /opt/snowos
rm -rf /etc/snowos
rm -rf /tmp/snowos_sockets

echo "[-] Removing users..."
userdel snowos-sys || true
userdel snowos-ai || true

echo "=========================================="
echo "✅ SnowOS Runtime successfully removed."
echo "   System restored to base Ubuntu state."
echo "=========================================="
