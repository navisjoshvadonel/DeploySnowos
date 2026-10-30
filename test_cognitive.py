import os, sys, time, json
import socket
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, "ai"))
sys.path.insert(0, os.path.expanduser("~/snowos/ai"))

# Setup mock environment with fallback for read-only sandboxes
desktop_dir = os.path.expanduser("~/Desktop")
archive_dir = os.path.expanduser("~/Archive/Vault")
try:
    os.makedirs(desktop_dir, exist_ok=True)
    probe = os.path.join(desktop_dir, ".probe")
    with open(probe, "w") as f: f.write("ok")
    os.remove(probe)
except (OSError, PermissionError):
    desktop_dir = "/tmp/Desktop"
    archive_dir = "/tmp/Archive/Vault"
    os.environ["SNOWOS_DESKTOP_DIR"] = desktop_dir
    os.environ["SNOWOS_ARCHIVE_DIR"] = archive_dir
    os.makedirs(desktop_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)

test_file = os.path.join(desktop_dir, "old_file.txt")
with open(test_file, "w") as f:
    f.write("test")

# Set access time to 10 days ago
old_time = time.time() - (10 * 86400)
os.utime(test_file, (old_time, old_time))

print("Testing NyxVFS Socket...")
socket_path = "/run/snowos/nyxvfs.sock"
if os.path.exists(socket_path):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(socket_path)
        s.sendall(json.dumps({"action": "purge_desktop"}).encode())
        data = s.recv(4096)
        s.close()
        print("Response from Daemon:", data.decode())
    except Exception as e:
        print("Daemon socket error:", e)
else:
    print("Daemon socket not found. Running engine directly...")
    from nyxvfs.vfs_engine import NyxVFS
    vfs = NyxVFS()
    res = vfs.purge_desktop()
    print("Purge Desktop Result:", res)

print("\nChecking if old file was archived...")
archive_path = os.path.join(archive_dir, "old_file.txt")
if os.path.exists(archive_path):
    print("SUCCESS: File was successfully archived.")
else:
    print("FAIL: File was NOT archived.")
