#!/usr/bin/env python3
# snowos/validation/injection/recovery_assertions.py

import subprocess
import time
import sys

def assert_safe_mode_triggered():
    """Verify that after 3 frostwm crashes, frostwm-safemode.service is active."""
    print("[*] Verifying Safe Mode transition...")
    for _ in range(10):
        result = subprocess.run(["systemctl", "is-active", "frostwm-safemode.service"], capture_output=True, text=True)
        if "active" in result.stdout:
            print("[+] PASS: Safe Mode triggered successfully.")
            return True
        time.sleep(1)
    
    print("[-] FAIL: Safe Mode did not trigger.")
    sys.exit(1)

def assert_tpm_blind_mode():
    """Verify that if TPM is missing, the AI broker enters Blind Mode."""
    print("[*] Verifying TPM Blind Mode...")
    # Check broker logs or state file
    try:
        with open("/runtime/broker/state", "r") as f:
            if "BLIND_MODE=1" in f.read():
                print("[+] PASS: Broker is in Blind Mode.")
                return True
    except FileNotFoundError:
        pass
    
    print("[-] FAIL: Broker failed to enter Blind Mode.")
    sys.exit(1)

def assert_rollback_integrity():
    """Verify that a corrupted system snapshot triggers a GRUB revert."""
    print("[*] Verifying Rollback Integrity...")
    # Check current mounted BTRFS subvolume
    result = subprocess.run(["findmnt", "-n", "-o", "OPTIONS", "/"], capture_output=True, text=True)
    if "subvol=@system_snapshot" in result.stdout:
         print("[+] PASS: System rolled back to previous snapshot.")
         return True
    print("[-] FAIL: System did not rollback.")
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: recovery_assertions.py <assertion_name>")
        sys.exit(1)
        
    func_name = sys.argv[1]
    if func_name in locals():
        locals()[func_name]()
    else:
        print(f"Unknown assertion: {func_name}")
