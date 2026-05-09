import sys
import os
import time

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from runtime.event_bus import bus
from runtime.state_manager import StateManager
from runtime.controller import RuntimeController

def test_runtime():
    print("--- Initializing Sentient Runtime ---")
    state = StateManager()
    controller = RuntimeController(state)
    
    # Mock UI listener
    def on_ui_change(mode):
        print(f"  [UI Hook] Mode changed to: {mode}")
    
    bus.subscribe("ui_mode_change", on_ui_change)
    
    print("\n--- Simulating CPU Spike (95%) ---")
    bus.publish("system_health", {"cpu": 95})
    
    # Wait for processing
    time.sleep(1)
    
    current_mode = state.get("mode")
    load = state.get("system_load")
    print(f"\nFinal State: Mode={current_mode}, Load={load}")
    
    if current_mode == "performance" and load == "high":
        print("\n✅ Verification Successful: High load correctly triggered Performance Mode.")
    else:
        print("\n❌ Verification Failed.")

if __name__ == "__main__":
    test_runtime()
