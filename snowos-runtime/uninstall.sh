#!/usr/bin/env bash
# ==============================================================================
# SnowOS Runtime Uninstaller (Delegates to Unified Transactional Rollback)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_ROLLBACK="$SCRIPT_DIR/../rollback.sh"

if [ -f "$ROOT_ROLLBACK" ]; then
  exec bash "$ROOT_ROLLBACK"
else
  echo "=========================================="
  echo " Uninstalling SnowOS Platform"
  echo "=========================================="

  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "Please run as root (sudo ./uninstall.sh)"
    exit 1
  fi

  for service in \
    snowos-frostbite.service \
    snowos-healbridge.service \
    snowos-governor.service \
    snowos-nyxvfs.service \
    snowos-updater.service \
    snowos-optimizer.service \
    snowos-control.service \
    snowos-aicore.service \
    snowos-sentinel.service \
    snowos-broker.service \
    snowos-boot.service; do
    systemctl stop "$service" 2>/dev/null || true
    systemctl disable "$service" 2>/dev/null || true
  done

  rm -f /etc/systemd/system/snowos-*.service
  rm -f /etc/tmpfiles.d/snowos.conf
  systemctl daemon-reload

  rm -rf /opt/snowos /etc/snowos /run/snowos /var/lib/snowos /var/log/snowos
  rm -f /usr/local/bin/snowos

  userdel snowos-sys 2>/dev/null || true
  userdel snowos-ai 2>/dev/null || true

  echo "=========================================="
  echo " SnowOS removed."
  echo "=========================================="
fi
