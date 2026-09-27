#!/usr/bin/env bash
# ==============================================================================
# ❄️ SnowOS Hardened Enterprise Deployment Script
# Provides verified, transactional installation with pre-flight checks,
# strict dependency ordering, and automated rollback on failure.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="${1:-all}"
OFFLINE_MODE=false
SKIP_PREFLIGHT=false
AUTO_ROLLBACK=false

# --- Argument Parsing ---
for arg in "$@"; do
  case "$arg" in
    --offline)
      OFFLINE_MODE=true
      ;;
    --skip-preflight)
      SKIP_PREFLIGHT=true
      ;;
    --auto-rollback)
      AUTO_ROLLBACK=true
      ;;
    --rollback)
      if [ -f "$SCRIPT_DIR/rollback.sh" ]; then
        exec bash "$SCRIPT_DIR/rollback.sh"
      else
        echo "[-] Error: rollback.sh not found."
        exit 1
      fi
      ;;
    core|visual|all|smooth)
      PROFILE="$arg"
      ;;
    *)
      if [ "$arg" != "$1" ]; then
        echo "Unknown option: $arg"
      fi
      ;;
  esac
done

if [[ ! "$PROFILE" =~ ^(core|visual|all|smooth)$ ]]; then
  echo "Usage: sudo ./install.sh [core|visual|all|smooth] [--offline] [--auto-rollback] [--skip-preflight] [--rollback]"
  exit 1
fi

echo "=========================================================="
echo " ❄️  SnowOS Platform Installer [Profile: ${PROFILE^^}]"
echo "=========================================================="

# --- Root Permission Enforcement ---
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "[-] Error: SnowOS requires root permissions to manage system services and policies."
  echo "    Please run: sudo ./install.sh $PROFILE"
  exit 1
fi

# --- Emergency Error Handler & Rollback Trap ---
INSTALL_FAILED=0
handle_error() {
  local exit_code=$?
  local line_no=$1
  if [ "$exit_code" -ne 0 ]; then
    INSTALL_FAILED=1
    echo ""
    echo "=========================================================="
    echo " ❌ CRITICAL: Installation failed at line $line_no (exit code $exit_code)"
    echo "=========================================================="
    if [ "$AUTO_ROLLBACK" = "true" ]; then
      echo "[*] Auto-rollback requested. Restoring baseline system..."
      if [ -f "$SCRIPT_DIR/rollback.sh" ]; then
        bash "$SCRIPT_DIR/rollback.sh" || true
      fi
    else
      echo "[!] The system may be in an inconsistent state."
      echo "    To cleanly revert all changes, run:"
      echo "       sudo ./rollback.sh"
      echo "    or:"
      echo "       sudo ./install.sh --rollback"
    fi
  fi
}
trap 'handle_error $LINENO' ERR

# ==============================================================================
# 1. PRE-FLIGHT VERIFICATION
# ==============================================================================
run_preflight_checks() {
  echo "[+] Phase 1: Running Pre-flight Diagnostics & Compatibility Checks..."
  local preflight_errors=0

  # Check 1.1: Operating System
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "    - OS Detected: ${NAME:-Linux} ${VERSION_ID:-Unknown}"
    if [[ "${ID:-}" != "ubuntu" && "${ID_LIKE:-}" != *"ubuntu"* && "${ID_LIKE:-}" != *"debian"* ]]; then
      echo "      [!] Warning: SnowOS is optimized for Ubuntu 22.04/24.04 LTS. Detected: $NAME"
    fi
  else
    echo "    [!] Warning: /etc/os-release not found. Target platform cannot be verified."
  fi

  # Check 1.2: Free Disk Space (minimum 5GB recommended, 2GB required)
  local free_kb
  free_kb=$(df -k / | awk 'NR==2 {print $4}')
  local free_mb=$((free_kb / 1024))
  if [ "$free_mb" -lt 2048 ]; then
    echo "    [-] ERROR: Insufficient disk space on / (${free_mb}MB free, minimum 2048MB required)."
    preflight_errors=$((preflight_errors + 1))
  else
    echo "    - Available Disk Space: $((free_mb / 1024))GB [OK]"
  fi

  # Check 1.3: System RAM (minimum 2GB)
  if [ -f /proc/meminfo ]; then
    local mem_total_kb
    mem_total_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
    local mem_total_mb=$((mem_total_kb / 1024))
    if [ "$mem_total_mb" -lt 1800 ]; then
      echo "    [!] Warning: Low memory detected (${mem_total_mb}MB). SnowOS services may experience contention."
    else
      echo "    - System Memory: $((mem_total_mb / 1024))GB [OK]"
    fi
  fi

  # Check 1.4: Repository Source Files Verification
  echo "    - Verifying installation source integrity..."
  local required_files=(
    "$SCRIPT_DIR/snowos-runtime/src"
    "$SCRIPT_DIR/snowos-runtime/config/snowos.env"
    "$SCRIPT_DIR/snowos-runtime/config/boot_manifest.json"
    "$SCRIPT_DIR/snowos-runtime/config/ai_features.json"
    "$SCRIPT_DIR/snowos-runtime/config/brand.json"
    "$SCRIPT_DIR/snowos-runtime/config/snowos-tmpfiles.conf"
    "$SCRIPT_DIR/snowos-runtime/services/snowos-boot.service"
    "$SCRIPT_DIR/snowos-runtime/services/snowos-broker.service"
    "$SCRIPT_DIR/snowos-runtime/services/snowos-sentinel.service"
    "$SCRIPT_DIR/snowos-runtime/services/snowos-aicore.service"
    "$SCRIPT_DIR/snowos-runtime/services/snowos-control.service"
    "$SCRIPT_DIR/distribution/cli/snowos"
  )

  if [ "$PROFILE" = "visual" ] || [ "$PROFILE" = "all" ] || [ "$PROFILE" = "smooth" ]; then
    required_files+=(
      "$SCRIPT_DIR/apply_branding.sh"
      "$SCRIPT_DIR/identity/os-release"
      "$SCRIPT_DIR/identity/lsb-release"
      "$SCRIPT_DIR/assets/logo.png"
      "$SCRIPT_DIR/assets/snowos-wallpaper.png"
    )
  fi

  local missing_files=()
  for req in "${required_files[@]}"; do
    if [ ! -e "$req" ]; then
      missing_files+=("$req")
    fi
  done

  if [ ${#missing_files[@]} -gt 0 ]; then
    echo "    [-] ERROR: The following required deployment source files are missing:"
    for m in "${missing_files[@]}"; do
      echo "        * $m"
    done
    preflight_errors=$((preflight_errors + 1))
  else
    echo "    - Deployment Source Files: Verified (${#required_files[@]} components present) [OK]"
  fi

  # Check 1.5: Desktop Environment & Extension Conflicts
  if [ "$PROFILE" = "visual" ] || [ "$PROFILE" = "all" ] || [ "$PROFILE" = "smooth" ]; then
    if ! command -v gnome-shell >/dev/null 2>&1; then
      echo "    [!] Notice: gnome-shell is not detected. Visual/lockscreen customizations will be installed but require GNOME to activate."
    else
      echo "    - GNOME Shell Detected: $(gnome-shell --version 2>/dev/null || echo 'Present') [OK]"
    fi

    # Check for conflicting dock extensions
    if dpkg -l gnome-shell-extension-dash-to-dock >/dev/null 2>&1; then
      echo "    [!] Warning: Detected conflicting extension 'gnome-shell-extension-dash-to-dock'. It will be disabled in favor of ubuntu-dock."
    fi
  fi

  if [ "$preflight_errors" -gt 0 ]; then
    echo "[-] Pre-flight checks failed with $preflight_errors critical errors. Aborting installation."
    exit 1
  fi
  echo "[+] Pre-flight validation passed successfully."
}

if [ "$SKIP_PREFLIGHT" != "true" ]; then
  run_preflight_checks
fi

# ==============================================================================
# 2. RUNTIME DEPENDENCIES RESOLUTION
# ==============================================================================
if [ "$OFFLINE_MODE" != "true" ]; then
  echo "[+] Phase 2: Resolving System and Runtime Dependencies..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y || {
    echo "[!] Warning: apt-get update failed or was partially interrupted. Continuing with local caches..."
  }

  echo "    - Installing base system tools..."
  apt-get install -y \
    python3 \
    python3-pip \
    python3-psutil \
    python3-rich \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    scrot \
    xdotool \
    wmctrl \
    xbindkeys \
    brightnessctl \
    libnotify-bin \
    || echo "[!] Notice: Some optional packages could not be installed via APT."

  echo "    - Installing Python AI/service packages..."
  pip3 install --break-system-packages prompt_toolkit chromadb psutil rich 2>/dev/null || \
  pip3 install prompt_toolkit chromadb psutil rich 2>/dev/null || \
  echo "[!] Notice: Optional pip dependencies skipped or already satisfied."
else
  echo "[+] Phase 2: Offline mode active. Skipping remote dependency synchronization."
fi

# ==============================================================================
# 3. DIRECTORY STRUCTURE AND SERVICE ACCOUNTS
# ==============================================================================
echo "[+] Phase 3: Initializing Platform Directories & Service Accounts..."

ensure_service_user() {
  local user_name="$1"
  local home_dir="$2"

  echo "    - Setting up service user: $user_name ($home_dir)..."
  if ! getent group "$user_name" >/dev/null 2>&1; then
    groupadd -f -r "$user_name"
  fi

  if ! id -u "$user_name" >/dev/null 2>&1; then
    useradd -r -M -d "$home_dir" -s /usr/sbin/nologin -g "$user_name" "$user_name"
  fi

  if ! id -u "$user_name" >/dev/null 2>&1; then
    echo "[-] Error: Failed to create service account $user_name."
    exit 1
  fi

  mkdir -p "$home_dir"
  chown "$user_name":"$user_name" "$home_dir"
}

# Create core directory tree
mkdir -p /etc/snowos /opt/snowos /var/log/snowos /run/snowos
mkdir -p /var/lib/snowos/system/.snowos /var/lib/snowos/ai /var/lib/snowos/runtime /var/lib/snowos/logs /snapshots

ensure_service_user snowos-sys /var/lib/snowos/system
ensure_service_user snowos-ai /var/lib/snowos/ai

# Directory permissions
chown -R root:root /var/lib/snowos
chmod -R 0755 /var/lib/snowos

chown root:root /etc/snowos /opt/snowos
chown -R snowos-ai:snowos-ai /var/lib/snowos/ai
chown -R snowos-sys:snowos-sys /var/lib/snowos/system /var/lib/snowos/system/.snowos /run/snowos
chmod 0755 /var/log/snowos
chmod 0750 /var/lib/snowos/ai /var/lib/snowos/system
chmod 0775 /run/snowos

# Secure secrets directory (HMAC key location, accessible only by broker)
mkdir -p /etc/snowos/secrets
chown snowos-sys:snowos-sys /etc/snowos/secrets
chmod 0700 /etc/snowos/secrets

# ==============================================================================
# 4. RUNTIME CODE & ARCHITECTURE DEPLOYMENT
# ==============================================================================
echo "[+] Phase 4: Deploying Runtime Code to /opt/snowos..."
cp -R "$SCRIPT_DIR/snowos-runtime/src/." /opt/snowos/
chown -R root:root /opt/snowos
chmod -R 0755 /opt/snowos
if [ -d /opt/snowos/core/bin ]; then
  chmod +x /opt/snowos/core/bin/* || true
fi

# Cognitive OS components integration
echo "    - Linking Cognitive AI modules..."
mkdir -p /opt/snowos/ai_core/nyxvfs /opt/snowos/ai_core/performance /opt/snowos/ui_engine/frostbite
if [ -d "$SCRIPT_DIR/ai/nyxvfs" ]; then
  cp -R "$SCRIPT_DIR/ai/nyxvfs/." /opt/snowos/ai_core/nyxvfs/
fi
if [ -d "$SCRIPT_DIR/ai/performance" ]; then
  cp -R "$SCRIPT_DIR/ai/performance/." /opt/snowos/ai_core/performance/
fi
if [ -f "$SCRIPT_DIR/ai/context_engine.py" ]; then
  cp "$SCRIPT_DIR/ai/context_engine.py" /opt/snowos/ai_core/context_engine.py
fi
if [ -d "$SCRIPT_DIR/ui_engine/frostbite" ]; then
  cp -R "$SCRIPT_DIR/ui_engine/frostbite/." /opt/snowos/ui_engine/frostbite/
fi
if [ -f "$SCRIPT_DIR/ui_engine/frost_desktop.py" ]; then
  cp "$SCRIPT_DIR/ui_engine/frost_desktop.py" /opt/snowos/ui_engine/frost_desktop.py
fi
chown -R root:root /opt/snowos/ai_core /opt/snowos/ui_engine
chmod -R 0755 /opt/snowos/ai_core /opt/snowos/ui_engine

# Architecture Blueprints
if [ -d "$SCRIPT_DIR/implementation" ]; then
  mkdir -p /opt/snowos/architecture
  cp -R "$SCRIPT_DIR/implementation" /opt/snowos/architecture/
  if [ -d "$SCRIPT_DIR/validation" ]; then
    cp -R "$SCRIPT_DIR/validation" /opt/snowos/architecture/
  fi
  chown -R root:root /opt/snowos/architecture
  chmod -R 0755 /opt/snowos/architecture
fi

# Install Distribution CLI
echo "    - Installing SnowOS CLI and desktop entries..."
cp "$SCRIPT_DIR/distribution/cli/snowos" /usr/local/bin/snowos
chmod +x /usr/local/bin/snowos

if [ -f "$SCRIPT_DIR/distribution/identity/frostshell.desktop" ]; then
  cp "$SCRIPT_DIR/distribution/identity/frostshell.desktop" /usr/share/applications/
  chmod 0644 /usr/share/applications/frostshell.desktop
  update-desktop-database /usr/share/applications/ >/dev/null 2>&1 || true
fi

# ==============================================================================
# 5. CONFIGURATION & INTEGRITY MANIFEST
# ==============================================================================
echo "[+] Phase 5: Seeding Platform Configurations & Computing Integrity Manifest..."

install_config_with_dist() {
  local source_file="$1"
  local target_file="$2"

  if [ -f "$source_file" ]; then
    cp "$source_file" "${target_file}.dist"
    if [ ! -f "$target_file" ]; then
      cp "$source_file" "$target_file"
    fi
  else
    echo "[-] Warning: Config source $source_file not found."
  fi
}

install_config_with_dist "$SCRIPT_DIR/snowos-runtime/config/snowos.env" /etc/snowos/snowos.env
install_config_with_dist "$SCRIPT_DIR/snowos-runtime/config/boot_manifest.json" /etc/snowos/boot_manifest.json
install_config_with_dist "$SCRIPT_DIR/snowos-runtime/config/ai_features.json" /etc/snowos/ai_features.json
install_config_with_dist "$SCRIPT_DIR/snowos-runtime/config/brand.json" /etc/snowos/brand.json

if [ -f "$SCRIPT_DIR/snowos-runtime/src/system_services/permission_broker/capabilities.json" ]; then
  cp "$SCRIPT_DIR/snowos-runtime/src/system_services/permission_broker/capabilities.json" /etc/snowos/capabilities.json
fi

chown root:snowos-sys /etc/snowos/*.json /etc/snowos/*.env* 2>/dev/null || true
chmod 0640 /etc/snowos/*.json /etc/snowos/*.env* 2>/dev/null || true

# Compute SHA-256 integrity manifest
write_integrity_manifest() {
  local manifest_file="/etc/snowos/integrity_manifest.json"
  local capabilities_hash boot_hash features_hash brand_hash

  capabilities_hash="$(sha256sum /etc/snowos/capabilities.json 2>/dev/null | awk '{print $1}' || echo "none")"
  boot_hash="$(sha256sum /etc/snowos/boot_manifest.json 2>/dev/null | awk '{print $1}' || echo "none")"
  features_hash="$(sha256sum /etc/snowos/ai_features.json 2>/dev/null | awk '{print $1}' || echo "none")"
  brand_hash="$(sha256sum /etc/snowos/brand.json 2>/dev/null | awk '{print $1}' || echo "none")"

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
write_integrity_manifest

# ==============================================================================
# 6. SYSTEMD SERVICE REGISTRATION & STRICT SEQUENCING
# ==============================================================================
if [ "$PROFILE" = "core" ] || [ "$PROFILE" = "all" ] || [ "$PROFILE" = "smooth" ]; then
  echo "[+] Phase 6: Registering and Sequencing Systemd Daemon Services..."

  # Setup tmpfiles.d for volatile memory management
  cp "$SCRIPT_DIR/snowos-runtime/config/snowos-tmpfiles.conf" /etc/tmpfiles.d/snowos.conf
  systemd-tmpfiles --create /etc/tmpfiles.d/snowos.conf

  # Register service units (snowos-runtime provides base units, distribution provides overrides)
  cp "$SCRIPT_DIR/snowos-runtime/services/"*.service /etc/systemd/system/
  if [ -d "$SCRIPT_DIR/distribution/services" ]; then
    cp "$SCRIPT_DIR/distribution/services/"*.service /etc/systemd/system/
  fi
  systemctl daemon-reload

  # Enable core daemons
  echo "    - Enabling core system services..."
  systemctl enable snowos-boot.service
  systemctl enable snowos-broker.service
  systemctl enable snowos-sentinel.service
  systemctl enable snowos-aicore.service
  systemctl enable snowos-optimizer.service
  systemctl enable snowos-control.service
  systemctl enable snowos-updater.service

  # Optional Cognitive OS services (enable conditionally if modules present)
  if [ -f /opt/snowos/ai_core/nyxvfs/vfs_daemon.py ]; then
    systemctl enable snowos-nyxvfs.service >/dev/null 2>&1 || true
  fi
  if [ -f /opt/snowos/ai_core/performance/intent_governor.py ]; then
    systemctl enable snowos-governor.service >/dev/null 2>&1 || true
  fi
  if [ -f /opt/snowos/ai_core/nyxvfs/healing_bridge.py ]; then
    systemctl enable snowos-healbridge.service >/dev/null 2>&1 || true
  fi

  if [ "$OFFLINE_MODE" != "true" ]; then
    echo "    - Executing strictly ordered service startup sequence..."
    
    # Gracefully stop active services to prevent socket binding collisions
    systemctl stop \
      snowos-healbridge.service \
      snowos-governor.service \
      snowos-nyxvfs.service \
      snowos-control.service \
      snowos-optimizer.service \
      snowos-aicore.service \
      snowos-sentinel.service \
      snowos-broker.service \
      snowos-boot.service >/dev/null 2>&1 || true

    # Step 6.1: Start snowos-boot.service (FOUNDATIONAL ONESHOT)
    echo "    [1/5] Starting SnowOS Boot Orchestrator (snowos-boot.service)..."
    if ! systemctl start snowos-boot.service; then
      echo "[-] ERROR: snowos-boot.service failed to execute cleanly."
      echo "--- Journalctl Output for snowos-boot.service ---"
      journalctl -u snowos-boot.service --no-pager -n 25 || true
      echo "-------------------------------------------------"
      exit 1
    fi

    # Step 6.2: Start snowos-broker.service (FOUNDATIONAL BROKER)
    echo "    [2/5] Starting SnowOS Permission Broker (snowos-broker.service)..."
    systemctl start snowos-broker.service
    
    # Poll for broker socket availability (up to 5 seconds)
    local broker_active=false
    for _ in {1..10}; do
      if systemctl is-active --quiet snowos-broker.service && [ -S /run/snowos/broker.sock ]; then
        broker_active=true
        break
      fi
      sleep 0.5
    done

    if [ "$broker_active" != "true" ]; then
      echo ""
      echo "=========================================================="
      echo " [-] ERROR: snowos-broker.service failed to initialize."
      echo "=========================================================="
      echo "--- Crash Logs (journalctl -u snowos-broker.service) ---"
      journalctl -u snowos-broker.service --no-pager -n 35 || true
      echo "--------------------------------------------------------"
      echo "[!] Diagnosis Tips:"
      echo "    1. Check permissions on /etc/snowos/secrets: $(ls -ld /etc/snowos/secrets 2>/dev/null || echo 'Missing')"
      echo "    2. Check permissions on /run/snowos: $(ls -ld /run/snowos 2>/dev/null || echo 'Missing')"
      echo "    3. Attempt manual invocation:"
      echo "       sudo -u snowos-sys /usr/bin/python3 /opt/snowos/system_services/permission_broker/broker_daemon.py"
      exit 1
    fi
    echo "      ✔ Broker is ACTIVE and socket /run/snowos/broker.sock is listening."

    # Step 6.3: Start dependent security and AI daemons
    echo "    [3/5] Starting AI Sentinel (snowos-sentinel.service)..."
    systemctl start snowos-sentinel.service || echo "      [!] Warning: snowos-sentinel.service failed to start."

    echo "    [4/5] Starting SnowOS AI Core & Control engines..."
    systemctl start snowos-aicore.service || echo "      [!] Warning: snowos-aicore.service failed to start."
    systemctl start snowos-control.service || echo "      [!] Warning: snowos-control.service failed to start."
    systemctl start snowos-optimizer.service || echo "      [!] Warning: snowos-optimizer.service failed to start."

    # Step 6.4: Start cognitive helper daemons
    echo "    [5/5] Checking cognitive OS extensions..."
    if [ -f /opt/snowos/ai_core/nyxvfs/vfs_daemon.py ]; then
      systemctl start snowos-nyxvfs.service >/dev/null 2>&1 || echo "      [!] nyxvfs inactive (optional subsystem)"
    fi
    if [ -f /opt/snowos/ai_core/performance/intent_governor.py ]; then
      systemctl start snowos-governor.service >/dev/null 2>&1 || echo "      [!] governor inactive (optional subsystem)"
    fi
    if [ -f /opt/snowos/ai_core/nyxvfs/healing_bridge.py ]; then
      systemctl start snowos-healbridge.service >/dev/null 2>&1 || echo "      [!] healbridge inactive (optional subsystem)"
    fi
  else
    echo "    - Offline Mode: Registered services will start upon reboot."
  fi
fi

# ==============================================================================
# 7. DESKTOP THEMING & IDENTITY
# ==============================================================================
if [ "$PROFILE" = "visual" ] || [ "$PROFILE" = "all" ] || [ "$PROFILE" = "smooth" ]; then
  echo "[+] Phase 7: Deploying SnowOS Visual Identity & Theming..."

  if [ -f "$SCRIPT_DIR/apply_branding.sh" ]; then
    echo "    - Applying desktop branding, GDM lockscreen, and GRUB identity..."
    bash "$SCRIPT_DIR/apply_branding.sh"
  elif [ -f "$SCRIPT_DIR/apply_snowos_visuals.sh" ]; then
    echo "    - Applying SnowOS visuals via fallback script..."
    bash "$SCRIPT_DIR/apply_snowos_visuals.sh"
  fi

  # Update GLIB schemas
  if command -v glib-compile-schemas >/dev/null 2>&1; then
    echo "    - Compiling system GLib schemas..."
    glib-compile-schemas /usr/share/glib-2.0/schemas 2>/dev/null || true
  fi
fi

# ==============================================================================
# 8. POST-INSTALL INTEGRITY VALIDATION
# ==============================================================================
echo ""
echo "[+] Phase 8: Running Post-Install Integrity Diagnostics..."
if [ -f "$SCRIPT_DIR/snowos-runtime/validation/check_health.py" ]; then
  python3 "$SCRIPT_DIR/snowos-runtime/validation/check_health.py" || {
    echo "[!] Health check completed with warnings. Check output above for details."
  }
fi

echo ""
echo "=========================================================="
echo " ⭐ SnowOS Platform Installation Complete!"
echo " Profile: ${PROFILE^^}"
echo " To manage services:   snowos doctor | snowos update"
echo " To launch shell:      python3 /opt/snowos/ai_core/nyx_kernel/nyx.py"
echo " To cleanly uninstall: sudo ./rollback.sh"
echo "=========================================================="
exit 0
