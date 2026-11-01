#!/usr/bin/env bash
# ==============================================================================
# ❄️ SnowOS Bootloader & GRUB Reliability Verification Suite
# Performs exhaustive diagnostics on UEFI/BIOS boot configurations,
# kernel/initrd pairings, GRUB drop-in syntax, early KMS, and video modes.
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo -e "${CYAN}${BOLD}==========================================================${NC}"
echo -e "${CYAN}${BOLD} ❄️  SnowOS Bootloader & GRUB Integrity Diagnostics${NC}"
echo -e "${CYAN}${BOLD}==========================================================${NC}"

# Check 1: Root Privileges
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo -e "${YELLOW}[!] Notice: Running without root privileges. Some hardware/NVRAM probes may be limited.${NC}"
fi

# Check 2: Boot Firmware Architecture
echo -e "\n${BOLD}[1/7] Probing Firmware Environment...${NC}"
if [ -d "/sys/firmware/efi" ]; then
    echo -e "    ${GREEN}✔ Firmware Mode: UEFI (64-bit modern)${NC}"
    EFI_MODE=true
    
    # Check EFI System Partition
    if mountpoint -q /boot/efi 2>/dev/null; then
        EFI_FS=$(findmnt -n -o FSTYPE /boot/efi 2>/dev/null || echo "unknown")
        EFI_FREE=$(df -m /boot/efi 2>/dev/null | awk 'NR==2 {print $4}')
        echo -e "    ${GREEN}✔ /boot/efi is mounted (${EFI_FS}, ${EFI_FREE}MB free)${NC}"
    else
        echo -e "    ${YELLOW}⚠ Notice: /boot/efi is not mounted as a separate mountpoint.${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Check efibootmgr availability
    if command -v efibootmgr >/dev/null 2>&1; then
        echo -e "    ${GREEN}✔ efibootmgr utility is installed.${NC}"
    else
        echo -e "    ${YELLOW}⚠ efibootmgr is missing. Install with: sudo apt install -y efibootmgr${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "    ${GREEN}✔ Firmware Mode: Legacy BIOS / CSM${NC}"
    EFI_MODE=false
fi

# Check 3: Kernel & Initramfs Verification
echo -e "\n${BOLD}[2/7] Checking Kernel Images & Initramfs Availability...${NC}"
KERNELS=(/boot/vmlinuz-*)

if [ -e "${KERNELS[0]:-}" ]; then
    echo -e "    ${GREEN}✔ Found ${#KERNELS[@]} kernel image(s) in /boot:${NC}"
    for k in "${KERNELS[@]}"; do
        KVER="${k#/boot/vmlinuz-}"
        MATCH_INITRD="/boot/initrd.img-${KVER}"
        if [ -f "$MATCH_INITRD" ]; then
            echo -e "        * ${BOLD}vmlinuz-${KVER}${NC} -> ${GREEN}initrd.img-${KVER} [Matched ✔]${NC}"
        else
            echo -e "        * ${BOLD}vmlinuz-${KVER}${NC} -> ${RED}initrd.img-${KVER} [MISSING ✖]${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    done
elif [ ! -d "/boot" ]; then
    echo -e "    ${YELLOW}⚠ Notice: Running in isolated container environment without mounted /boot directory.${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "    ${RED}✖ CRITICAL: No /boot/vmlinuz-* kernel images found!${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check 4: /boot Storage Capacity
echo -e "\n${BOLD}[3/7] Checking /boot Filesystem Capacity...${NC}"
if [ -d "/boot" ]; then
    BOOT_FREE_MB=$(df -m /boot 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
else
    BOOT_FREE_MB=$(df -m / 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
fi

if [ "$BOOT_FREE_MB" -lt 50 ]; then
    echo -e "    ${RED}✖ /boot is low on space: ${BOOT_FREE_MB}MB free (minimum 50MB required).${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "    ${GREEN}✔ Available boot partition space: ${BOOT_FREE_MB}MB [OK]${NC}"
fi

# Check 5: GRUB Configuration & Drop-ins
echo -e "\n${BOLD}[4/7] Validating GRUB Configuration & Drop-in Directives...${NC}"

# Check drop-in config
GRUB_CFG_SNOWOS="/etc/default/grub.d/50-snowos.cfg"
if [ -f "$GRUB_CFG_SNOWOS" ]; then
    echo -e "    ${GREEN}✔ SnowOS drop-in found: $GRUB_CFG_SNOWOS${NC}"
else
    echo -e "    ${YELLOW}⚠ Warning: $GRUB_CFG_SNOWOS not found.${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check invalid terminal output (terminal_output "gfxterm console" errors in UEFI)
TERMINAL_OUT=$(grep -s "^GRUB_TERMINAL_OUTPUT=" /etc/default/grub "$GRUB_CFG_SNOWOS" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"' || true)
if [[ "$TERMINAL_OUT" == *"console"* ]] && [ "$EFI_MODE" = "true" ]; then
    echo -e "    ${RED}✖ Detected 'console' in GRUB_TERMINAL_OUTPUT for UEFI: '${TERMINAL_OUT}'.${NC}"
    echo -e "      In UEFI, terminal 'console' is unsupported and triggers boot errors. Must be 'gfxterm'.${NC}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "    ${GREEN}✔ GRUB Terminal Output is safe: '${TERMINAL_OUT:-default}' [OK]${NC}"
fi

# Check timeout and style (ensure user is not trapped in hidden 0s timeout)
TIMEOUT_STYLE=$(grep -s "^GRUB_TIMEOUT_STYLE=" /etc/default/grub "$GRUB_CFG_SNOWOS" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"' || true)
TIMEOUT_SEC=$(grep -s "^GRUB_TIMEOUT=" /etc/default/grub "$GRUB_CFG_SNOWOS" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"' || true)

if [ "$TIMEOUT_STYLE" = "hidden" ] && [ "${TIMEOUT_SEC:-0}" -eq 0 ]; then
    echo -e "    ${YELLOW}⚠ Warning: GRUB timeout is hidden with 0s. Boot menu will not be visible on failure.${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "    ${GREEN}✔ GRUB Menu Timeout: ${TIMEOUT_SEC:-5}s (Style: ${TIMEOUT_STYLE:-menu}) [OK]${NC}"
fi

# Check Recovery Mode
DISABLE_RECOVERY=$(grep -s "^GRUB_DISABLE_RECOVERY=" /etc/default/grub "$GRUB_CFG_SNOWOS" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"' || true)
if [ "$DISABLE_RECOVERY" = "true" ]; then
    echo -e "    ${YELLOW}⚠ Warning: GRUB recovery entries are disabled.${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "    ${GREEN}✔ GRUB Recovery & Advanced options enabled [OK]${NC}"
fi

# Check Background Image Existence
GRUB_BG=$(grep -s "^GRUB_BACKGROUND=" /etc/default/grub "$GRUB_CFG_SNOWOS" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"' || true)
if [ -n "$GRUB_BG" ]; then
    if [ -f "$GRUB_BG" ]; then
        BG_SIZE_KB=$(du -k "$GRUB_BG" | cut -f1)
        echo -e "    ${GREEN}✔ GRUB Background Image verified: $GRUB_BG (${BG_SIZE_KB}KB) [OK]${NC}"
    else
        echo -e "    ${RED}✖ GRUB_BACKGROUND points to non-existent file: $GRUB_BG${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "    ${YELLOW}ℹ Notice: No GRUB_BACKGROUND explicitly configured.${NC}"
fi

# Check 6: Early KMS Virtual Machine Display Drivers
echo -e "\n${BOLD}[5/7] Checking Early KMS Display Driver Modules in Initramfs...${NC}"
INITRAMFS_MODS="/etc/initramfs-tools/modules"
if [ -f "$INITRAMFS_MODS" ]; then
    VM_MODS=("vboxvideo" "vmwgfx" "virtio_gpu" "qxl" "bochs_drm")
    FOUND_MODS=()
    for mod in "${VM_MODS[@]}"; do
        if grep -qx "$mod" "$INITRAMFS_MODS"; then
            FOUND_MODS+=("$mod")
        fi
    done
    if [ ${#FOUND_MODS[@]} -ge 3 ]; then
        echo -e "    ${GREEN}✔ Virtual Machine early KMS modules present in initramfs (${FOUND_MODS[*]}) [OK]${NC}"
    else
        echo -e "    ${YELLOW}⚠ Some VM display modules are missing from $INITRAMFS_MODS.${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "    ${YELLOW}ℹ Notice: $INITRAMFS_MODS not found.${NC}"
fi

# Check 7: GRUB Config Generator Dry Run
echo -e "\n${BOLD}[6/7] Testing GRUB Configuration Generator (update-grub dry run)...${NC}"
if command -v grub-mkconfig >/dev/null 2>&1; then
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        TMP_GRUB_OUT=$(mktemp /tmp/grub_test.XXXXXX)
        if grub-mkconfig -o "$TMP_GRUB_OUT" >/dev/null 2>&1; then
            ENTRY_COUNT=$(grep -c "^menuentry " "$TMP_GRUB_OUT" || true)
            echo -e "    ${GREEN}✔ grub-mkconfig completed with exit code 0. Generated $ENTRY_COUNT menu entry/entries.${NC}"
        else
            echo -e "    ${RED}✖ grub-mkconfig failed to execute cleanly! Review syntax in /etc/default/grub.${NC}"
            ERRORS=$((ERRORS + 1))
        fi
        rm -f "$TMP_GRUB_OUT"
    else
        echo -e "    ${YELLOW}ℹ Dry-run grub-mkconfig skipped (requires root privileges).${NC}"
    fi
else
    echo -e "    ${RED}✖ grub-mkconfig binary not found!${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo -e "\n${BOLD}[7/7] Diagnostics Summary${NC}"
echo -e "=========================================================="
if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e " ${GREEN}${BOLD}⭐ PASS: SnowOS Bootloader & GRUB configuration is 100% HEALTHY!${NC}"
    echo -e " The operating system is fully configured to boot without GRUB issues."
    echo -e "=========================================================="
    exit 0
elif [ "$ERRORS" -eq 0 ]; then
    echo -e " ${YELLOW}${BOLD}⚠ NOTICE: Passed with $WARNINGS warning(s). Boot should proceed normally.${NC}"
    echo -e " Review the warnings above if you encounter non-fatal anomalies."
    echo -e "=========================================================="
    exit 0
else
    echo -e " ${RED}${BOLD}❌ FAIL: Detected $ERRORS critical boot issue(s) and $WARNINGS warning(s).${NC}"
    echo -e " GRUB may fail to load until the critical issues listed above are resolved."
    echo -e "=========================================================="
    exit 1
fi
