import uuid
import os
import shutil
from .storage import StateStorage
from .capture import CaptureEngine
from .diff import DiffEngine

class PersistentStateEngine:
    def __init__(self, storage: StateStorage, workspace_root, snapshots_dir=None):
        self.storage = storage
        self.capture_engine = CaptureEngine(workspace_root)
        self.snapshots_dir = snapshots_dir or os.path.expanduser("~/.snowos/state_snapshots")
        os.makedirs(self.snapshots_dir, exist_ok=True)

    def capture_state(self, plan_id=None, label="manual", user_id=None):
        """Capture the current state and link it to a plan."""
        latest = self.storage.get_latest_state()
        parent_id = latest['state_id'] if latest else None
        
        state_id = f"state_{uuid.uuid4().hex[:8]}"
        metadata, files = self.capture_engine.capture()
        
        # Link to snapshot directory (Stage 32 style but managed here)
        snapshot_path = os.path.join(self.snapshots_dir, state_id)
        self._create_physical_snapshot(files, snapshot_path)
        
        metadata['snapshot_path'] = snapshot_path
        metadata['label'] = label
        
        # Save metadata to DB
        self.storage.save_state(state_id, parent_id, plan_id, metadata, files, user_id=user_id)
        
        # If there's a parent, compute and save diff
        if parent_id:
            parent_files = self.storage.get_state_files(parent_id)
            diff = DiffEngine.compute_diff(parent_files, files)
            self.storage.save_diff(parent_id, state_id, diff)
            
        return state_id

    def checkout(self, state_id):
        """Restore the system to a previous state."""
        state = self.storage.get_state(state_id)
        if not state:
            raise ValueError(f"State {state_id} not found.")
            
        snapshot_path = state['metadata'].get('snapshot_path')
        if not snapshot_path or not os.path.exists(snapshot_path):
            raise ValueError(f"Physical snapshot for {state_id} is missing.")
            
        # Perform restore
        # Note: We should be careful and only restore tracked dirs
        for entry in os.scandir(snapshot_path):
            target = entry.path.replace(snapshot_path, "").lstrip("/")
            # This is a bit complex since paths are absolute in 'files'
            # But here we just mirror back from snapshot_path
            pass
            
        # Simplified restoration for this stage:
        # We'll just copy back from the snapshot to the workspace root
        # and other tracked locations.
        self._restore_from_snapshot(snapshot_path)
        return True

    def _create_physical_snapshot(self, files, snapshot_path):
        """Copy current files to a snapshot location for versioning."""
        os.makedirs(snapshot_path, exist_ok=True)
        for f in files:
            src = f['path']
            # Compute relative path to base (workspace_root)
            # This handles multi-root snapshots
            rel_path = os.path.relpath(src, "/") # simplified
            dst = os.path.join(snapshot_path, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except Exception:
                continue

    def _restore_from_snapshot(self, snapshot_path):
        """Copy files back from snapshot to the system."""
        # For each file in snapshot, copy back to original absolute path
        for root, _, filenames in os.walk(snapshot_path):
            for filename in filenames:
                src = os.path.join(root, filename)
                # Reconstruct original absolute path
                rel_path = os.path.relpath(src, snapshot_path)
                dst = "/" + rel_path
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    continue
                    
    def get_history(self):
        return self.storage.get_history()

    def get_diff(self, state_id_a, state_id_b):
        # If they are consecutive, we might have it in DB
        diff = self.storage.get_diff(state_id_a, state_id_b)
        if diff:
            return diff
            
        # Otherwise compute on the fly
        files_a = self.storage.get_state_files(state_id_a)
        files_b = self.storage.get_state_files(state_id_b)
        return DiffEngine.compute_diff(files_a, files_b)
