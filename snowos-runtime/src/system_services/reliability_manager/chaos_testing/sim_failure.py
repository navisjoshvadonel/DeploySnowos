import sys
import os
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from snapshot_engine.snapshotter import SnapshotEngine
from rollback_controller.rollback import RollbackController
from integrity_checker.trust_boot import TrustBoot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run_chaos_test():
    print("\n--- SNOWOS RELIABILITY & CHAOS TEST ---")
    
    snapshotter = SnapshotEngine()
    rollback = RollbackController()
    trust_boot = TrustBoot()
    
    # 1. Take a safe snapshot
    print("\n[Phase 1: Establishing Safe State]")
    snapshotter.create_snapshot()
    time.sleep(1)
    
    # 2. Chaos Injection: Corrupt capabilities.json
    print("\n[Phase 2: Injecting Chaos (Corrupting Permission Broker Manifest)]")
    target_file = "/home/develop/snowos/system_services/permission_broker/capabilities.json"
    with open(target_file, "a") as f:
        f.write("\nMALICIOUS_INJECTION_OR_CORRUPTION")
    print("-> Target corrupted.")
    
    # 3. Simulate System Reboot
    print("\n[Phase 3: Simulated Reboot & Trust Boot]")
    is_safe = trust_boot.verify_system_integrity()
    
    if not is_safe:
        print("-> Trust Boot halted execution.")
        # Trigger Rollback
        rollback.trigger_rollback(reason="Boot integrity check failed.")
        
    # 4. Verify Recovery
    print("\n[Phase 4: Post-Rollback Verification]")
    is_safe_now = trust_boot.verify_system_integrity()
    if is_safe_now:
        print("-> SUCCESS: System fully recovered from catastrophic failure.")
    else:
        print("-> FAILED: System remains unrecoverable.")
        
    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    run_chaos_test()
