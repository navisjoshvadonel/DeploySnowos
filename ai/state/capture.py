import os
import hashlib
import time
import subprocess
import json
from pathlib import Path

class CaptureEngine:
    def __init__(self, workspace_root, tracked_dirs=None):
        self.workspace_root = os.path.abspath(workspace_root)
        # Default to common SnowOS config and workspace paths
        self.tracked_dirs = tracked_dirs or [
            self.workspace_root,
            os.path.expanduser("~/.snowos"),
            "/etc/snowos" # if exists
        ]

    def capture(self):
        """Capture the current system state metadata."""
        files = []
        for base_dir in self.tracked_dirs:
            if not os.path.exists(base_dir):
                continue
                
            for root, _, filenames in os.walk(base_dir):
                # Skip common ignore patterns
                if any(x in root for x in [".git", "__pycache__", "venv", "node_modules"]):
                    continue
                    
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    try:
                        files.append(self._get_file_metadata(filepath))
                    except (PermissionError, FileNotFoundError):
                        continue

        metadata = {
            "env": dict(os.environ),
            "packages": self._get_installed_packages(),
            "uptime": self._get_uptime()
        }
        
        return metadata, files

    def _get_file_metadata(self, filepath):
        stat = os.stat(filepath)
        return {
            "path": filepath,
            "hash": self._compute_hash(filepath),
            "size": stat.st_size,
            "modified_time": stat.st_mtime
        }

    def _compute_hash(self, filepath):
        """Generate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                # Read in chunks for efficiency
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return "hash_error"

    def _get_installed_packages(self):
        """Collect apt and pip package lists."""
        packages = {"apt": [], "pip": []}
        try:
            # Apt
            apt_out = subprocess.check_output(["dpkg-query", "-W", "-f=${Package}==${Version}\n"], text=True)
            packages["apt"] = apt_out.strip().split("\n")
            
            # Pip
            pip_out = subprocess.check_output(["pip", "list", "--format=freeze"], text=True)
            packages["pip"] = pip_out.strip().split("\n")
        except Exception:
            pass
        return packages

    def _get_uptime(self):
        try:
            with open('/proc/uptime', 'r') as f:
                return float(f.readline().split()[0])
        except Exception:
            return 0.0
