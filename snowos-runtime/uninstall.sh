#!/bin/bash
set -e

echo "=========================================="
echo " Uninstalling SnowOS Platform"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./uninstall.sh)"
  exit 1
fi

for service in \
  snowos-broker.service \
  snowos-sentinel.service \
  snowos-aicore.service \
  snowos-optimizer.service \
  snowos-control.service
do
  systemctl stop "$service" || true
  systemctl disable "$service" || true
done

rm -f /etc/systemd/system/snowos-*.service
systemctl daemon-reload

rm -rf /opt/snowos
rm -rf /etc/snowos
rm -rf /run/snowos

userdel snowos-sys || true
userdel snowos-ai || true

echo "=========================================="
echo " SnowOS removed."
echo "=========================================="
