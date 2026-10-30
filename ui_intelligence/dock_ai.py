import logging

class DockAI:
    """Manages the behavior and ordering of the Glacier Dock."""
    
    def __init__(self):
        self.default_apps = ["terminal", "vscode", "browser", "files", "spotify"]
        self.current_order = list(self.default_apps)
        self.logger = logging.getLogger("SnowOS.DockAI")

    def highlight_predicted(self, app_name):
        """Trigger a visual glow on the predicted app icon."""
        self.logger.info(f"Dock: Highlighting {app_name}")
        from runtime.event_bus import bus
        bus.publish("ui_dock_update", {"action": "glow", "app": app_name})

    def reorder_by_intent(self, intent):
        """Move the most relevant apps to the center of the dock."""
        new_order = list(self.current_order)
        
        if intent == "coding":
            priority = ["vscode", "terminal"]
        elif intent == "media":
            priority = ["spotify"]
        elif intent == "browsing":
            priority = ["browser"]
        else:
            priority = []

        for app in reversed(priority):
            if app in new_order:
                new_order.remove(app)
                new_order.insert(0, app)
        
        if new_order != self.current_order:
            self.current_order = new_order
            self.logger.info(f"Dock: Reordered for {intent} -> {new_order}")
            from runtime.event_bus import bus
            bus.publish("ui_dock_update", {"action": "reorder", "apps": self.current_order})
