import os
import shutil
import uuid
import time
from .storage import DELStorage

class SnapshotSystem:
    def __init__(self, storage: DELStorage, base_path="/var/snowos/snapshots"):
        self.storage = storage
        self.base_path = base_path
        # Fallback to local path if /var is not writable
        if not os.access(os.path.dirname(self.base_path), os.W_OK):
            self.base_path = os.path.expanduser("~/.snowos/snapshots")
        
        os.makedirs(self.base_path, exist_ok=True)

    def capture(self, plan_id, target_dir):
        """Capture a snapshot of the target directory."""
        snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
        snapshot_path = os.path.join(self.base_path, snapshot_id)
        
        if os.path.exists(target_dir):
            shutil.copytree(target_dir, snapshot_path)
            self.storage.save_snapshot(snapshot_id, plan_id, snapshot_path)
            return snapshot_id
        return None

    def restore(self, snapshot_id, target_dir):
        """Restore the target directory from a snapshot."""
        snapshot = self.storage.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found.")
            
        snapshot_path = snapshot["path"]
        if not os.path.exists(snapshot_path):
            raise ValueError(f"Snapshot path {snapshot_path} does not exist.")
            
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
            
        shutil.copytree(snapshot_path, target_dir)
        return True
