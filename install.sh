#!/bin/bash
set -e

PROFILE="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$PROFILE" in
  core|visual|all|smooth)
    ;;
  *)
    echo "Usage: sudo ./install.sh [core|visual|all|smooth]"
    exit 1
    ;;
esac

echo "=========================================="
echo " Installing SnowOS Platform ($PROFILE)"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./install.sh $PROFILE)"
  exit 1
fi

ensure_service_user() {
  local user_name="$1"
  local home_dir="$2"

  if ! id -u "$user_name" >/dev/null 2>&1; then
    useradd -r -m -d "$home_dir" -s /usr/sbin/nologin "$user_name"
  fi
}

install_config_with_dist() {
  local source_file="$1"
  local target_file="$2"

  cp "$source_file" "${target_file}.dist"
  if [ ! -f "$target_file" ]; then
    cp "$source_file" "$target_file"
  fi
}

write_integrity_manifest() {
  local manifest_file="/etc/snowos/integrity_manifest.json"
  local capabilities_hash
  local boot_hash
  local features_hash
  local brand_hash

  capabilities_hash="$(sha256sum /etc/snowos/capabilities.json | awk '{print $1}')"
  boot_hash="$(sha256sum /etc/snowos/boot_manifest.json | awk '{print $1}')"
  features_hash="$(sha256sum /etc/snowos/ai_features.json | awk '{print $1}')"
  brand_hash="$(sha256sum /etc/snowos/brand.json | awk '{print $1}')"

  cat > "$manifest_file" <<EOF
{
  "schema": "snowos.integrity.manifest.v1",
  "generated_by": "snowos-install",
  "tracked_files": [
    {
      "path": "/etc/snowos/capabilities.json",
      "sha256": "$capabilities_hash"
    },
    {
      "path": "/etc/snowos/boot_manifest.json",
      "sha256": "$boot_hash"
    },
    {
      "path": "/etc/snowos/ai_features.json",
      "sha256": "$features_hash"
    },
    {
      "path": "/etc/snowos/brand.json",
      "sha256": "$brand_hash"
    }
  ]
}
EOF

  chown root:snowos-sys "$manifest_file"
  chmod 0640 "$manifest_file"
}

ensure_service_user snowos-sys /var/lib/snowos/system
ensure_service_user snowos-ai /var/lib/snowos/ai

# Explicitly create all required directories
echo "[+] Creating SnowOS directory structure..."
mkdir -p /etc/snowos /opt/snowos /var/log/snowos /run/snowos
mkdir -p /var/lib/snowos/system /var/lib/snowos/ai /var/lib/snowos/runtime /var/lib/snowos/logs

# Fix permissions
chown root:root /etc/snowos /opt/snowos
chown -R snowos-ai:snowos-ai /var/lib/snowos/ai
chown -R snowos-sys:snowos-sys /var/lib/snowos/system /run/snowos
chmod 0755 /var/lib/snowos /var/log/snowos
chmod 0750 /var/lib/snowos/ai /var/lib/snowos/system /run/snowos

# Secure secrets directory — only root can read/write
# The broker generates its HMAC key here on first boot.
echo "[+] Setting up SnowOS secrets directory..."
mkdir -p /etc/snowos/secrets
chown root:root /etc/snowos/secrets
chmod 0700 /etc/snowos/secrets

echo "[+] Deploying SnowOS runtime to /opt/snowos..."
cp -R "$SCRIPT_DIR/snowos-runtime/src/." /opt/snowos/
chown -R root:root /opt/snowos

echo "[+] Installing SnowOS platform defaults..."
install_config_with_dist "$SCRIPT_DIR/snowos-runtime/config/snowos.env" /etc/snowos/snowos.env
cp "$SCRIPT_DIR/snowos-runtime/config/boot_manifest.json" /etc/snowos/boot_manifest.json
cp "$SCRIPT_DIR/snowos-runtime/config/boot_manifest.json" /etc/snowos/boot_manifest.json.dist
cp "$SCRIPT_DIR/snowos-runtime/config/ai_features.json" /etc/snowos/ai_features.json
cp "$SCRIPT_DIR/snowos-runtime/config/ai_features.json" /etc/snowos/ai_features.json.dist
cp "$SCRIPT_DIR/snowos-runtime/config/brand.json" /etc/snowos/brand.json
cp "$SCRIPT_DIR/snowos-runtime/config/brand.json" /etc/snowos/brand.json.dist
cp "$SCRIPT_DIR/snowos-runtime/src/system_services/permission_broker/capabilities.json" /etc/snowos/capabilities.json
chown root:snowos-sys \
  /etc/snowos/snowos.env \
  /etc/snowos/snowos.env.dist \
  /etc/snowos/boot_manifest.json \
  /etc/snowos/boot_manifest.json.dist \
  /etc/snowos/ai_features.json \
  /etc/snowos/ai_features.json.dist \
  /etc/snowos/brand.json \
  /etc/snowos/brand.json.dist \
  /etc/snowos/capabilities.json
chmod 0640 \
  /etc/snowos/snowos.env \
  /etc/snowos/snowos.env.dist \
  /etc/snowos/boot_manifest.json \
  /etc/snowos/boot_manifest.json.dist \
  /etc/snowos/ai_features.json \
  /etc/snowos/ai_features.json.dist \
  /etc/snowos/brand.json \
  /etc/snowos/brand.json.dist \
  /etc/snowos/capabilities.json
write_integrity_manifest

if [ "$PROFILE" = "core" ] || [ "$PROFILE" = "all" ] || [ "$PROFILE" = "smooth" ]; then
  # 3. Configurations
  echo "[+] Copying configurations..."
  cp /opt/snowos/system_services/permission_broker/capabilities.json /etc/snowos/
  chown snowos-sys:snowos-sys /etc/snowos/capabilities.json

  # 3.5 Distribution Components
  echo "[+] Installing SnowOS CLI and Apps..."
  cp ./distribution/cli/snowos /usr/local/bin/snowos
  chmod +x /usr/local/bin/snowos
  if [ -f "./distribution/identity/frostshell.desktop" ]; then
    cp ./distribution/identity/frostshell.desktop /usr/share/applications/
    chmod 0644 /usr/share/applications/frostshell.desktop
    update-desktop-database /usr/share/applications/ || true
  fi

  # 4. Service Registration
  echo "[+] Registering systemd services..."
  cp ./snowos-runtime/services/*.service /etc/systemd/system/
  cp ./distribution/services/*.service /etc/systemd/system/
  systemctl daemon-reload

  echo "[+] Enabling services..."
  systemctl enable snowos-broker.service
  systemctl enable snowos-sentinel.service
  systemctl enable snowos-aicore.service
  systemctl enable snowos-optimizer.service
  systemctl enable snowos-control.service
  systemctl enable snowos-updater.service

  # We don't start them immediately in the script to allow manual verification,
  # or we can start them.
  echo "[+] Starting core services..."
  systemctl start snowos-broker.service || echo "Broker start deferred"
  systemctl start snowos-sentinel.service || echo "Sentinel start deferred"
  systemctl start snowos-updater.service || echo "Updater start deferred"
  systemctl start snowos-aicore.service || echo "SnowOS AI Core start deferred"
  systemctl restart snowos-control.service || echo "SnowControl start deferred"
fi

if [ "$PROFILE" = "visual" ] || [ "$PROFILE" = "all" ] || [ "$PROFILE" = "smooth" ]; then
  echo "[+] Installing SnowOS visual dependencies..."
  apt-get update -y
  apt-get install -y gnome-shell-extension-dash-to-dock gnome-tweaks python3-rich papirus-icon-theme || true

  echo "[+] Applying SnowOS Aurora branding..."
  bash "$SCRIPT_DIR/apply_branding.sh"
fi

echo "=========================================="
echo " SnowOS installation complete."
echo " Core profile:    sudo ./install.sh core"
echo " Visual profile:  sudo ./install.sh visual"
echo " Full profile:    sudo ./install.sh all"
echo " Smooth install:  sudo ./install.sh smooth"
echo " Validation:      python3 snowos-runtime/validation/check_health.py"
echo "=========================================="
