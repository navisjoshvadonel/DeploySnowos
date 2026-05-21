import os, sys, time, json
import socket
from pathlib import Path

# Setup mock environment
os.makedirs(os.path.expanduser("~/Downloads"), exist_ok=True)
os.makedirs(os.path.expanduser("~/Desktop"), exist_ok=True)
with open(os.path.expanduser("~/Desktop/old_file.txt"), "w") as f:
    f.write("test")

# Set access time to 10 days ago
old_time = time.time() - (10 * 86400)
os.utime(os.path.expanduser("~/Desktop/old_file.txt"), (old_time, old_time))

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
    sys.path.insert(0, os.path.expanduser("~/snowos/ai"))
    from nyxvfs.vfs_engine import NyxVFS
    vfs = NyxVFS()
    res = vfs.purge_desktop()
    print("Purge Desktop Result:", res)

print("\nChecking if old file was archived...")
archive_path = os.path.expanduser("~/Archive/Vault/old_file.txt")
if os.path.exists(archive_path):
    print("SUCCESS: File was successfully archived.")
else:
    print("FAIL: File was NOT archived.")

