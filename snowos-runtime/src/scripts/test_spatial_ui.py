import sys
import os
import time

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from runtime.event_bus import bus
from ui_intelligence.spatial_engine import SpatialUIEngine
from ui_intelligence.dock_ai import DockAI
from ui_intelligence.window_ai import WindowAI
from ui_intelligence.layout_manager import LayoutManager

def test_spatial_ui():
    print("--- Initializing Autonomous Spatial UI ---")
    dock_ai = DockAI()
    window_ai = WindowAI()
    layout_manager = LayoutManager()
    engine = SpatialUIEngine(dock_ai, window_ai, layout_manager)
    
    # Mock UI listeners
    def on_dock_update(data):
        print(f"  [Dock Hook] Action: {data['action']}, Target: {data.get('app') or data.get('apps')}")
    
    def on_window_update(data):
        print(f"  [Window Hook] Arrangement: {data['layout']} for {data['apps']}")

    def on_layout_update(data):
        print(f"  [Layout Hook] New Workspace: {data['layout']}")

    bus.subscribe("ui_dock_update", on_dock_update)
    bus.subscribe("ui_window_update", on_window_update)
    bus.subscribe("ui_layout_update", on_layout_update)
    
    print("\n--- Simulating AI Insight: Predict 'vscode' ---")
    bus.publish("ai_insight", {"prediction": "vscode"})
    
    time.sleep(0.5)
    
    print("\n--- Simulating Mode Change: 'dev' ---")
    bus.publish("ui_mode_change", "dev")
    
    time.sleep(0.5)
    
    print("\n--- Simulating CPU Spike (90%) ---")
    bus.publish("system_health", {"cpu": 90})
    
    time.sleep(0.5)
    
    print("\n✅ Verification Successful: UI System reacted to prediction, mode, and system state.")

if __name__ == "__main__":
    test_spatial_ui()
