import os
import subprocess
import json

RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
BOOT_STATUS_FILE = os.environ.get("SNOWOS_BOOT_STATUS_FILE", os.path.join(RUNTIME_DIR, "boot-status.json"))
FEATURE_FLAGS_FILE = os.environ.get("SNOWOS_FEATURE_FLAGS_FILE", os.path.join(RUNTIME_DIR, "feature-flags.json"))
INTEGRITY_MANIFEST_FILE = os.environ.get("SNOWOS_INTEGRITY_MANIFEST_FILE", "/etc/snowos/integrity_manifest.json")


def check_service(service_name):
    try:
        status = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        ).stdout.strip()

        if status == "active":
            print(f"[OK] {service_name} is running")
            return True

        print(f"[ERR] {service_name} is offline (status: {status})")
        return False
    except Exception as exc:
        print(f"[ERR] Error checking {service_name}: {exc}")
        return False


def check_sockets():
    sockets = [
        os.path.join(RUNTIME_DIR, "broker.sock"),
        os.path.join(RUNTIME_DIR, "sentinel.sock"),
    ]
    all_good = True
    for socket_path in sockets:
        if os.path.exists(socket_path):
            print(f"[OK] Socket {socket_path} is active")
        else:
            print(f"[ERR] Socket {socket_path} is missing")
            all_good = False
    return all_good


def check_json_file(file_path, label, required_keys=None):
    required_keys = required_keys or []
    if not os.path.exists(file_path):
        print(f"[ERR] {label} missing: {file_path}")
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERR] {label} unreadable: {exc}")
        return False

    missing_keys = [key for key in required_keys if key not in payload]
    if missing_keys:
        print(f"[ERR] {label} missing keys: {', '.join(missing_keys)}")
        return False

    print(f"[OK] {label} available at {file_path}")
    return True


if __name__ == "__main__":
    print("--- SnowOS Runtime Health Check ---\n")

    print("[INFO] Validating /opt/snowos deployment...")
    layers = ["kernel_layer", "system_services", "ai_core", "ui_engine", "app_layer"]
    for layer in layers:
        layer_path = f"/opt/snowos/{layer}"
        if os.path.exists(layer_path):
            print(f"[OK] Layer {layer_path} deployed")
        else:
            print(f"[ERR] Layer {layer_path} missing")

    print("\n[INFO] Checking core services...")
    for service in [
        "snowos-boot.service",
        "snowos-broker.service",
        "snowos-sentinel.service",
        "snowos-aicore.service",
        "snowos-control.service",
    ]:
        check_service(service)

    print("\n[INFO] Checking runtime sockets...")
    check_sockets()

    print("\n[INFO] Checking SnowOS boot artifacts...")
    check_json_file(BOOT_STATUS_FILE, "Boot status", ["profile", "status", "feature_count"])
    check_json_file(FEATURE_FLAGS_FILE, "Feature flags", ["profile", "enabled"])
    check_json_file(INTEGRITY_MANIFEST_FILE, "Integrity manifest", ["tracked_files"])

    print("\n--- Validation Complete ---")
