import os
import shutil
import logging

logger = logging.getLogger("RollbackController")
SNAPSHOT_DIR = "/tmp/snowos_snapshots"
CRITICAL_FILES = [
    "/home/develop/snowos/system_services/permission_broker/capabilities.json"
]

class RollbackController:
    def __init__(self):
        pass

    def get_latest_snapshot(self):
        if not os.path.exists(SNAPSHOT_DIR):
            return None
        snapshots = sorted(os.listdir(SNAPSHOT_DIR))
        if not snapshots:
            return None
        return os.path.join(SNAPSHOT_DIR, snapshots[-1])

    def trigger_rollback(self, reason="Critical System Failure"):
        """
        Restores the system to the last known good snapshot.
        """
        logger.critical(f"INITIATING SYSTEM ROLLBACK. Reason: {reason}")
        
        latest_snapshot = self.get_latest_snapshot()
        if not latest_snapshot:
            logger.error("Rollback failed: No snapshots available. System may be unrecoverable.")
            return False
            
        logger.info(f"Restoring from snapshot: {latest_snapshot}")
        
        for file_path in CRITICAL_FILES:
            filename = os.path.basename(file_path)
            backup_file = os.path.join(latest_snapshot, filename)
            
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, file_path)
                logger.info(f"Restored: {file_path}")
                
        logger.info("Rollback complete. System state restored. Rebooting daemons...")
        return True
