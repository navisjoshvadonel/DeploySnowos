#!/usr/bin/env python3
import argparse
import subprocess
import os
import sys
import time

RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")

def print_header(title):
    print(f"\n\033[1;36m=== {title} ===\033[0m")

def cmd_status(args):
    print_header("SnowOS Status")
    
    # 1. Check Identity
    identity = "Unknown"
    try:
        with open("/etc/os-release", "r") as f:
            content = f.read()
            if 'PRETTY_NAME="SnowOS Aurora 24.04"' in content:
                identity = "SnowOS Aurora 24.04 (Active)"
            else:
                identity = "Ubuntu Base (Branding Missing)"
    except Exception:
        pass
    print(f"Identity: \033[1;32m{identity}\033[0m")
    
    # 2. Check Services
    print("\n\033[1mCore Daemons:\033[0m")
    services = [
        "snowos-broker.service",
        "snowos-sentinel.service",
        "snowos-aicore.service",
        "snowos-control.service",
    ]
    for srv in services:
        status = subprocess.run(["systemctl", "is-active", srv], capture_output=True, text=True).stdout.strip()
        if status == "active":
            print(f"  [\033[1;32mOK\033[0m] {srv}")
        else:
            print(f"  [\033[1;31m{status.upper()}\033[0m] {srv}")
            
    # 3. Check Sockets
    print("\n\033[1mIPC Sockets:\033[0m")
    sockets = [
        os.path.join(RUNTIME_DIR, "broker.sock"),
        os.path.join(RUNTIME_DIR, "sentinel.sock")
    ]
    for sock in sockets:
        if os.path.exists(sock):
            print(f"  [\033[1;32mOK\033[0m] {os.path.basename(sock)}")
        else:
            print(f"  [\033[1;31mMISSING\033[0m] {os.path.basename(sock)}")

def cmd_service(args):
    action = args.action
    name = args.name
    
    if not name.startswith("snowos-"):
        name = f"snowos-{name}"
    if not name.endswith(".service"):
        name = f"{name}.service"
        
    print(f"Executing '{action}' on {name}...")
    try:
        subprocess.run(["sudo", "systemctl", action, name], check=True)
        print(f"\033[1;32mSuccessfully executed {action} on {name}.\033[0m")
    except subprocess.CalledProcessError:
        print(f"\033[1;31mFailed to {action} {name}. Please check permissions or system logs.\033[0m")

def cmd_update(args):
    print_header("SnowOS Atomic Update (Mock Pipeline)")
    print("Fetching update manifests from upstream...")
    time.sleep(1)
    print("[\033[1;32mOK\033[0m] Update available: SnowOS Core v1.0.4-alpha")
    
    print("\nInitiating atomic update sequence:")
    time.sleep(0.5)
    print("1. Taking pre-update BTRFS snapshot: @system-snapshot-pre-1.0.4")
    time.sleep(1.5)
    print("2. Downloading OTA differential image...")
    for i in range(10, 101, 30):
        sys.stdout.write(f"\r  Progress: [{('#' * (i//10)).ljust(10)}] {i}%")
        sys.stdout.flush()
        time.sleep(0.5)
    print("\n3. Verifying image signatures... [\033[1;32mVERIFIED\033[0m]")
    time.sleep(0.5)
    print("4. Staging update to inactive subvolume (@system-next)")
    time.sleep(1)
    print("5. Updating GRUB bootloader entries...")
    time.sleep(0.5)
    
    print("\n\033[1;32mUpdate staged successfully.\033[0m")
    print("The system will boot into the new image on the next restart.")
    print("Use 'snowos rollback' from the boot menu if the new image fails.")

def main():
    parser = argparse.ArgumentParser(description="SnowOS System Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Status subcommand
    parser_status = subparsers.add_parser("status", help="Check SnowOS health, services, and identity")
    parser_status.set_defaults(func=cmd_status)
    
    # Service subcommand
    parser_service = subparsers.add_parser("service", help="Manage SnowOS core daemons")
    parser_service.add_argument("action", choices=["start", "stop", "restart", "status"], help="Action to perform")
    parser_service.add_argument("name", help="Name of the service (e.g., broker, aicore)")
    parser_service.set_defaults(func=cmd_service)
    
    # Update subcommand
    parser_update = subparsers.add_parser("update", help="Run the atomic OTA update mock pipeline")
    parser_update.set_defaults(func=cmd_update)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
