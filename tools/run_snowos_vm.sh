#!/usr/bin/env bash
# ==============================================================================
# ❄️ SnowOS QEMU/KVM Virtual Machine Launcher & Test Rig
# Tests SnowOS live hybrid ISO or virtual disk image with hardware acceleration
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RAM="${SNOWOS_VM_RAM:-4G}"
CPUS="${SNOWOS_VM_CPUS:-2}"
PORT="${SNOWOS_VM_PORT:-8000}"

echo "=========================================================="
echo " ❄️  SnowOS Virtual Machine Environment Launcher"
echo "=========================================================="

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
    echo "[-] Error: qemu-system-x86_64 is not installed."
    echo "    To install: sudo apt install -y qemu-system-x86 ovmf"
    exit 1
fi

# Locate ISO candidate
ISO_PATH="${1:-}"
if [ -z "$ISO_PATH" ]; then
    CANDIDATES=(
        "$WORKSPACE_ROOT/distribution/build/build-env/live-image-amd64.hybrid.iso"
        "$WORKSPACE_ROOT/distribution/build/snowos.iso"
        "$WORKSPACE_ROOT/snowos.iso"
    )
    for c in "${CANDIDATES[@]}"; do
        if [ -f "$c" ]; then
            ISO_PATH="$c"
            break
        fi
    done
fi

if [ -z "$ISO_PATH" ] || [ ! -f "$ISO_PATH" ]; then
    echo "[!] No ISO image found or specified."
    echo "    Usage: $0 [path/to/snowos.iso]"
    echo ""
    echo "    To build a SnowOS ISO first:"
    echo "      cd distribution/build && ./iso_builder.sh"
    exit 1
fi

echo "[+] Target Image: $ISO_PATH ($(du -h "$ISO_PATH" | cut -f1))"
echo "[+] Memory: $RAM | CPU Cores: $CPUS"
echo "[+] SnowControl Port Forward: http://127.0.0.1:${PORT}"

# KVM Acceleration check
ACCEL_ARGS=()
if [ -e /dev/kvm ] && [ -w /dev/kvm ]; then
    echo "[+] Hardware acceleration: KVM enabled (/dev/kvm)"
    ACCEL_ARGS+=("-enable-kvm" "-cpu" "host")
else
    echo "[!] Hardware acceleration: KVM not accessible, running with TCG software emulation"
    ACCEL_ARGS+=("-cpu" "max")
fi

# Launch QEMU with virtio graphics, sound, and network port-forwarding
echo "[*] Launching SnowOS in QEMU..."
exec qemu-system-x86_64 \
    "${ACCEL_ARGS[@]}" \
    -m "$RAM" \
    -smp "$CPUS" \
    -cdrom "$ISO_PATH" \
    -boot d \
    -vga virtio \
    -display default,show-cursor=on \
    -netdev user,id=net0,hostfwd=tcp::"${PORT}"-:8000 \
    -device virtio-net-pci,netdev=net0 \
    -device intel-hda -device hda-duplex \
    "$@"
