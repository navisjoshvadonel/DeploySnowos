import sys
import os
import json
import logging

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from ui_intelligence.layout_manager import LayoutManager

# Setup logging to stdout
logging.basicConfig(level=logging.INFO)

def test_layout_sync():
    state_file = "/home/develop/snowos/nyx/ui_state.json"
    lm = LayoutManager(state_path=state_file)
    
    print("--- Testing LayoutManager State Sync ---")
    
    # 1. Simulate High Stress
    print("\nSimulating High Stress (0.9)...")
    with open(state_file, 'w') as f:
        json.dump({"system_stress": 0.9}, f)
    
    lm.sync_with_state()
    if lm.active_layout == "minimal_black":
        print("✅ Correctly transitioned to 'performance' (minimal_black) layout.")
    else:
        print(f"❌ Failed transition. Current layout: {lm.active_layout}")

    # 2. Simulate Low Stress
    print("\nSimulating Low Stress (0.1)...")
    with open(state_file, 'w') as f:
        json.dump({"system_stress": 0.1}, f)
    
    lm.sync_with_state()
    if lm.active_layout == "ambient":
        print("✅ Correctly transitioned back to 'calm' (ambient) layout.")
    else:
        print(f"❌ Failed transition. Current layout: {lm.active_layout}")

if __name__ == "__main__":
    test_layout_sync()
