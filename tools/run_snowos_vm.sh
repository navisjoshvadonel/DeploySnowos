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

# Argument parsing for optional UEFI testing
USE_UEFI=false
EXTRA_ARGS=()
ISO_PATH=""

for arg in "$@"; do
    case "$arg" in
        --uefi)
            USE_UEFI=true
            ;;
        *)
            if [ -z "$ISO_PATH" ] && [ -f "$arg" ]; then
                ISO_PATH="$arg"
            else
                EXTRA_ARGS+=("$arg")
            fi
            ;;
    esac
done

# Locate ISO candidate if not passed
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
    echo "    Usage: $0 [path/to/snowos.iso] [--uefi]"
    echo ""
    echo "    Options:"
    echo "      --uefi   Boot VM in UEFI mode using OVMF firmware (tests EFI GRUB)"
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

# UEFI OVMF firmware configuration
UEFI_ARGS=()
if [ "$USE_UEFI" = "true" ]; then
    OVMF_CANDIDATES=(
        "/usr/share/OVMF/OVMF_CODE.fd"
        "/usr/share/ovmf/OVMF.fd"
        "/usr/share/qemu/OVMF.fd"
        "/usr/share/edk2-ovmf/x64/OVMF_CODE.fd"
    )
    OVMF_FOUND=""
    for ovmf in "${OVMF_CANDIDATES[@]}"; do
        if [ -f "$ovmf" ]; then
            OVMF_FOUND="$ovmf"
            break
        fi
    done
    if [ -n "$OVMF_FOUND" ]; then
        echo "[+] UEFI Mode: Enabled via OVMF firmware ($OVMF_FOUND)"
        UEFI_ARGS+=("-bios" "$OVMF_FOUND" "-machine" "q35")
    else
        echo "[!] Warning: OVMF firmware not found. Install with: sudo apt install -y ovmf"
        echo "    Falling back to standard BIOS mode."
    fi
else
    echo "[+] Firmware Mode: Legacy BIOS (Use --uefi to test UEFI GRUB loading)"
fi

# Launch QEMU with virtio graphics, sound, and network port-forwarding
echo "[*] Launching SnowOS in QEMU..."
exec qemu-system-x86_64 \
    "${ACCEL_ARGS[@]}" \
    "${UEFI_ARGS[@]}" \
    -m "$RAM" \
    -smp "$CPUS" \
    -cdrom "$ISO_PATH" \
    -boot d \
    -vga virtio \
    -display default,show-cursor=on \
    -netdev user,id=net0,hostfwd=tcp::"${PORT}"-:8000 \
    -device virtio-net-pci,netdev=net0 \
    -device intel-hda -device hda-duplex \
    "${EXTRA_ARGS[@]}"
