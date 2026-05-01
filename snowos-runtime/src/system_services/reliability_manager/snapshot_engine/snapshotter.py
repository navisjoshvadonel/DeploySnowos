import os
import shutil
import time
import logging

logger = logging.getLogger("SnapshotEngine")
SNAPSHOT_DIR = "/tmp/snowos_snapshots"
CRITICAL_FILES = [
    "/home/develop/snowos/system_services/permission_broker/capabilities.json"
]

class SnapshotEngine:
    def __init__(self):
        if not os.path.exists(SNAPSHOT_DIR):
            os.makedirs(SNAPSHOT_DIR)

    def create_snapshot(self):
        """
        Creates an atomic backup of critical system states.
        """
        timestamp = int(time.time())
        snapshot_path = os.path.join(SNAPSHOT_DIR, f"snapshot_{timestamp}")
        os.makedirs(snapshot_path)
        
        for file_path in CRITICAL_FILES:
            if os.path.exists(file_path):
                shutil.copy2(file_path, snapshot_path)
                
        logger.info(f"System state snapshot created at: {snapshot_path}")
        return snapshot_path
