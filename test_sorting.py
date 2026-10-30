import os, sys, time, json
from pathlib import Path

# Add local ai directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, "ai"))
sys.path.insert(0, os.path.expanduser("~/snowos/ai"))

from nyxvfs.vfs_engine import NyxVFS

vfs = NyxVFS()

# Create Context
with open("/tmp/snowos_context.json", "w") as f:
    json.dump({"active_app": "Banking", "window_title": "1040 Tax Info - Bank of America"}, f)

# Create mock download file with resilient path fallback
downloads = os.path.expanduser("~/Downloads")
try:
    os.makedirs(downloads, exist_ok=True)
    test_probe = os.path.join(downloads, ".probe")
    with open(test_probe, "w") as f:
        f.write("probe")
    os.remove(test_probe)
except (OSError, PermissionError):
    downloads = "/tmp/Downloads"
    os.makedirs(downloads, exist_ok=True)

mock_pdf = os.path.join(downloads, "scan_492.pdf")
with open(mock_pdf, "w") as f:
    f.write("CONFIDENTIAL: Here are the tax returns for the 2026 fiscal year...")

# Trigger Categorization
print("Simulating Nyx File Arrival...")
vfs._delayed_categorize(mock_pdf)

# Check results
ghosts = vfs.get_ghost_info(mock_pdf)
print("Ghost Metadata Registry:", ghosts)

if os.path.islink(mock_pdf):
    print("SUCCESS: Ghost Symlink left in Downloads:", mock_pdf, "->", os.readlink(mock_pdf))
else:
    print("FAIL: Ghost link not created.")
