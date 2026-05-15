#!/usr/bin/env bash
set -e

echo "[+] Step 1: Identifying target system user profile..."
TARGET_USER=$(grep "User=" /etc/systemd/system/snowos-broker.service | cut -d'=' -f2 | tr -d '[:space:]')
if [ -z "$TARGET_USER" ]; then TARGET_USER="snowos"; fi

echo "[+] Step 2: Injecting RuntimeDirectory rules into core unit specifications..."
SERVICES=(
    "/etc/systemd/system/snowos-boot.service"
    "/etc/systemd/system/snowos-broker.service"
    "/etc/systemd/system/snowos-control.service"
    "/etc/systemd/system/snowos-aicore.service"
    "/etc/systemd/system/snowos-sentinel.service"
)

for SERVICE in "${SERVICES[@]}"; do
    if [ -f "$SERVICE" ]; then
        echo "Updating configuration for: $SERVICE"
        # Strip existing RuntimeDirectory lines if present to prevent duplicates
        sudo sed -i '/^RuntimeDirectory=/d' "$SERVICE"
        sudo sed -i '/^RuntimeDirectoryMode=/d' "$SERVICE"
        
        # Inject modern systemd volatile memory management rules under the [Service] section
        sudo sed -i "/\[Service\]/a RuntimeDirectory=snowos\nRuntimeDirectoryMode=0775" "$SERVICE"
    fi
done

echo "[+] Step 3: Forcing directory sync for immediate initialization..."
sudo mkdir -p /run/snowos /var/log/snowos /etc/snowos
sudo chown -R "$TARGET_USER":"$TARGET_USER" /run/snowos /var/log/snowos
sudo chmod 775 /run/snowos

echo "[+] Step 4: Refreshing systemd unit configuration trees..."
sudo systemctl daemon-reload
sudo systemctl reset-failed

echo "[+] Step 5: Bootstrapping orchestration layer in correct dependency order..."
echo "Starting boot manager..." && sudo systemctl restart snowos-boot.service
echo "Starting communication broker..." && sudo systemctl restart snowos-broker.service
echo "Starting security sentinel..." && sudo systemctl restart snowos-sentinel.service
echo "Starting control engine..." && sudo systemctl restart snowos-control.service
echo "Starting intelligence layer..." && sudo systemctl restart snowos-aicore.service

echo "[+] Step 6: Querying runtime platform diagnostic metrics..."
cd ~/snowos
sudo python3 snowos-runtime/validation/check_health.py
