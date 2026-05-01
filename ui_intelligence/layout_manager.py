import logging

class LayoutManager:
    """Manages high-level UI workspaces and transitions."""
    
    def __init__(self, state_path="/home/develop/snowos/nyx/ui_state.json"):
        self.logger = logging.getLogger("SnowOS.LayoutManager")
        self.state_path = state_path
        self.layouts = {
            "calm": "ambient",
            "dev": "focused_split",
            "performance": "minimal_black",
            "media": "immersive",
            "safe": "minimalist_safe"
        }
        self.active_layout = "ambient"

    def sync_with_state(self):
        """Poll the UI state and adjust layout accordingly."""
        import json
        import os
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r') as f:
                    state = json.load(f)
                    stress = state.get("system_stress", 0.0)
                    if stress > 0.8:
                        self.select_layout("performance")
                    elif stress < 0.2:
                        self.select_layout("calm")
            except Exception as e:
                self.logger.error(f"LayoutManager: Failed to sync state: {e}")

    def select_layout(self, mode):
        """Transition the OS to a new visual workspace."""
        new_layout = self.layouts.get(mode, "ambient")
        if new_layout != self.active_layout:
            self.logger.info(f"LayoutManager: Transitioning to '{new_layout}' workspace (Mode: {mode})")
            self.active_layout = new_layout
            
            try:
                from runtime.event_bus import bus
                bus.publish("ui_layout_update", {
                    "action": "transition",
                    "layout": new_layout,
                    "animation": "static" if mode == "safe" else "glacier_slide"
                })
            except ImportError:
                self.logger.warning("LayoutManager: EventBus not available for transition broadcast.")

    def enter_safe_mode(self):
        """Force the UI into the safest, most stable state."""
        self.logger.warning("LayoutManager: Entering SAFE MODE due to system instability.")
        self.select_layout("safe")

    def apply_minimal_profile(self):
        self.select_layout("performance")

