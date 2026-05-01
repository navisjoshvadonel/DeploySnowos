import sys
import os

# Add nyx to path
sys.path.append(os.path.expanduser("~/snowos"))
sys.path.append(os.path.expanduser("~/snowos/nyx"))

from nyx.deterministic.semantic_fs import SemanticFS
from nyx.scheduler.engine import SchedulerEngine, TaskPriority

class MockAgent:
    def __init__(self):
        self.nyx_dir = os.path.expanduser("~/snowos/nyx")

def test_final_features():
    print("--- Testing SemanticFS Cloud Sync ---")
    agent = MockAgent()
    sfs = SemanticFS(agent)
    
    test_file = "/home/develop/snowos/scripts/test_security.py"
    sfs.sync_to_cloud(test_file)
    print(f"File: {test_file}")
    print(f"Is Ghost: {sfs.is_ghost(test_file)}")
    print(f"Metadata: {sfs.contexts['ghost_files'][test_file]}")

    print("\n--- Testing Predictive Scheduling Heuristics ---")
    sched = SchedulerEngine()
    
    # Normal task
    task1 = {"id": "t1", "description": "list files", "priority": TaskPriority.LOW}
    limits1 = sched._predict_cost(task1)
    print(f"Task: {task1['description']}")
    print(f"Predicted Limits: {limits1}")
    
    # Heavy task (should trigger scale-up)
    task2 = {"id": "t2", "description": "build and compile kernel modules", "priority": TaskPriority.LOW}
    limits2 = sched._predict_cost(task2)
    print(f"\nTask: {task2['description']}")
    print(f"Predicted Limits: {limits2}")
    
    if limits2['cpu_quota'] > limits1['cpu_quota']:
        print("\n✅ SUCCESS: Predictive engine scaled up for heavy task.")
    else:
        print("\n❌ FAILURE: Predictive engine did not scale up.")

if __name__ == "__main__":
    test_final_features()
