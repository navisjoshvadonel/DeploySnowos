#!/bin/bash
set -e

PROFILE="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

OFFLINE_MODE=false
if [ "$2" = "--offline" ] || [ "$3" = "--offline" ]; then
  OFFLINE_MODE=true
fi

case "$PROFILE" in
  core|visual|all|smooth)
    ;;
  *)
    echo "Usage: sudo ./install.sh [core|visual|all|smooth] [--offline]"
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

echo "[+] Verifying Python/Runtime Dependencies..."
apt-get update -y || true
apt-get install -y python3 || true
# Cognitive OS tools
apt-get install -y \
  python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  scrot xdotool wmctrl xbindkeys \
  brightnessctl libnotify-bin \
  || true

ensure_service_user() {
  local user_name="$1"
  local home_dir="$2"

  echo "[*] Ensuring service user $user_name exists..."
  if ! getent group "$user_name" >/dev/null 2>&1; then
    groupadd -f -r "$user_name"
  fi

  if ! id -u "$user_name" >/dev/null 2>&1; then
    useradd -r -M -d "$home_dir" -s /usr/sbin/nologin -g "$user_name" "$user_name"
  fi
  
  # Verify user creation
  if ! id -u "$user_name" >/dev/null 2>&1; then
    echo "[!] Critical Error: Failed to create user $user_name"
    exit 1
  fi

  mkdir -p "$home_dir"
  chown "$user_name":"$user_name" "$home_dir"
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

# Explicitly create all required directories
echo "[+] Creating SnowOS directory structure..."
mkdir -p /etc/snowos /opt/snowos /var/log/snowos /run/snowos
mkdir -p /var/lib/snowos/system /var/lib/snowos/ai /var/lib/snowos/runtime /var/lib/snowos/logs

ensure_service_user snowos-sys /var/lib/snowos/system
ensure_service_user snowos-ai /var/lib/snowos/ai

# Fix base ownership first
chown -R root:root /var/lib/snowos
chmod -R 0755 /var/lib/snowos

# Fix permissions
chown root:root /etc/snowos /opt/snowos
chown -R snowos-ai:snowos-ai /var/lib/snowos/ai
chown -R snowos-sys:snowos-sys /var/lib/snowos/system /run/snowos
chmod 0755 /var/log/snowos
chmod 0750 /var/lib/snowos/ai /var/lib/snowos/system
chmod 0775 /run/snowos

# Secure secrets directory — only root can read/write
# The broker generates its HMAC key here on first boot.
# Secure secrets directory — only the broker (snowos-sys) can write here
echo "[+] Setting up SnowOS secrets directory..."
mkdir -p /etc/snowos/secrets
chown snowos-sys:snowos-sys /etc/snowos/secrets
chmod 0700 /etc/snowos/secrets

echo "[+] Deploying SnowOS runtime to /opt/snowos..."
cp -R "$SCRIPT_DIR/snowos-runtime/src/." /opt/snowos/
chown -R root:root /opt/snowos
chmod -R 0755 /opt/snowos
chmod +x /opt/snowos/core/bin/* || true

echo "[+] Deploying SnowOS Cognitive OS modules..."
# NyxVFS + Healing Bridge
mkdir -p /opt/snowos/ai_core/nyxvfs
cp -R "$SCRIPT_DIR/ai/nyxvfs/." /opt/snowos/ai_core/nyxvfs/
# Intent Governor
mkdir -p /opt/snowos/ai_core/performance
cp -R "$SCRIPT_DIR/ai/performance/." /opt/snowos/ai_core/performance/
# Context Engine (upgraded)
cp "$SCRIPT_DIR/ai/context_engine.py" /opt/snowos/ai_core/context_engine.py
# Frostbite UI widget
mkdir -p /opt/snowos/ui_engine/frostbite
cp -R "$SCRIPT_DIR/ui_engine/frostbite/." /opt/snowos/ui_engine/frostbite/
# Upgraded desktop
cp "$SCRIPT_DIR/ui_engine/frost_desktop.py" /opt/snowos/ui_engine/frost_desktop.py
chown -R root:root /opt/snowos/ai_core /opt/snowos/ui_engine
chmod -R 0755 /opt/snowos/ai_core /opt/snowos/ui_engine

echo "[+] Deploying SnowOS Architectural Blueprints..."
if [ -d "$SCRIPT_DIR/implementation" ]; then
    mkdir -p /opt/snowos/architecture
    cp -R "$SCRIPT_DIR/implementation" /opt/snowos/architecture/
    cp -R "$SCRIPT_DIR/validation" /opt/snowos/architecture/ || true
    chown -R root:root /opt/snowos/architecture
    chmod -R 0755 /opt/snowos/architecture
fi

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
  echo "[+] Setting up systemd-tmpfiles for volatile memory..."
  cp ./snowos-runtime/config/snowos-tmpfiles.conf /etc/tmpfiles.d/snowos.conf
  systemd-tmpfiles --create /etc/tmpfiles.d/snowos.conf

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
  # Cognitive OS services
  systemctl enable snowos-nyxvfs.service   || true
  systemctl enable snowos-governor.service || true
  systemctl enable snowos-healbridge.service || true

  # Strict service restart order (Agent Recovery)
  if [ "$OFFLINE_MODE" != "true" ]; then
    echo "[+] Applying safe restart order for core services..."
    systemctl stop snowos-broker.service snowos-sentinel.service snowos-updater.service snowos-aicore.service snowos-control.service snowos-optimizer.service >/dev/null 2>&1 || true
    
    systemctl daemon-reload
    systemctl start snowos-broker.service
    
    echo "[*] Waiting for broker to initialize..."
    sleep 2

    if systemctl is-active --quiet snowos-broker.service; then
        echo "[+] Broker is ACTIVE, starting dependent services..."
        systemctl start snowos-sentinel.service
        systemctl start snowos-aicore.service
        systemctl start snowos-control.service
        # Cognitive OS daemons (non-critical — log but don't abort)
        systemctl start snowos-nyxvfs.service   || echo "[!] nyxvfs not started (non-critical)"
        systemctl start snowos-governor.service || echo "[!] governor not started (non-critical)"
        systemctl start snowos-healbridge.service || echo "[!] healbridge not started (non-critical)"
    else
        echo "[!] Broker failed to start. Printing crash logs:"
        echo "---------------------------------------------------"
        journalctl -u snowos-broker.service --no-pager -n 30 || true
        echo "---------------------------------------------------"
        echo "[!] Stopping chain immediately."
        exit 1
    fi
  else
    echo "[*] Offline mode: Skipping service start sequence."
  fi
fi

if [ "$PROFILE" = "visual" ] || [ "$PROFILE" = "all" ] || [ "$PROFILE" = "smooth" ]; then
  echo "[+] Installing SnowOS visual dependencies..."
  add-apt-repository universe -y
  apt-get update -y
  apt-get install -y gnome-shell-extension-ubuntu-dock gnome-tweaks python3-rich papirus-icon-theme || true
  apt-get remove -y gnome-shell-extension-dash-to-dock || true

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
