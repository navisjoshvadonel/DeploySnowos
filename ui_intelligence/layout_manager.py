import logging

class LayoutManager:
    """Manages high-level UI workspaces and transitions."""
    
    def __init__(self):
        self.logger = logging.getLogger("SnowOS.LayoutManager")
        self.layouts = {
            "calm": "ambient",
            "dev": "focused_split",
            "performance": "minimal_black",
            "media": "immersive"
        }
        self.active_layout = "ambient"

    def select_layout(self, mode):
        """Transition the OS to a new visual workspace."""
        new_layout = self.layouts.get(mode, "ambient")
        if new_layout != self.active_layout:
            self.active_layout = new_layout
            self.logger.info(f"LayoutManager: Transitioning to '{new_layout}' workspace")
            
            from runtime.event_bus import bus
            bus.publish("ui_layout_update", {
                "action": "transition",
                "layout": new_layout,
                "animation": "glacier_slide"
            })

    def apply_minimal_profile(self):
        self.select_layout("performance")
