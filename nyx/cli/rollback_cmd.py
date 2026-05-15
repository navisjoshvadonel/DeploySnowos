import os
from deterministic import DELStorage, SnapshotSystem

def rollback_command(snapshot_id, target_dir, db_path="nyx_deterministic.db"):
    storage = DELStorage(db_path=db_path)
    system = SnapshotSystem(storage)
    try:
        print(f"Rolling back to snapshot {snapshot_id}...")
        system.restore(snapshot_id, target_dir)
        print("Rollback successful.")
    except Exception as e:
        print(f"Rollback failed: {e}")
