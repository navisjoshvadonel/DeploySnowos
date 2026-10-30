import logging
import os
import sys

# Ensure parent dirs are in path for runtime imports
sys.path.append(os.path.expanduser("~/.snowos"))

try:
    from runtime.event_bus import bus
except ImportError:
    # Fallback for localized testing
    class MockBus:
        def subscribe(self, *args): pass
        def publish(self, *args): pass
    bus = MockBus()

class SpatialUIEngine:
    """The central intelligence hub for structural UI reorganization."""
    
    def __init__(self, dock_ai, window_ai, layout_manager):
        self.dock = dock_ai
        self.window = window_ai
        self.layout = layout_manager
        self.logger = logging.getLogger("SnowOS.SpatialEngine")
        self._setup_listeners()

    def _setup_listeners(self):
        # Listen for intent and prediction to pre-reshape the UI
        bus.subscribe("ai_insight", self._on_prediction)
        bus.subscribe("ui_mode_change", self._on_mode_change)
        bus.subscribe("user_intent", self._on_intent_change)
        bus.subscribe("system_health", self._on_health_check)

    def _on_prediction(self, data):
        prediction = data.get("prediction")
        if prediction:
            self.logger.info(f"Spatial Optimization: Preparing for '{prediction}'")
            self.dock.highlight_predicted(prediction)
            self.window.propose_arrangement_for(prediction)

    def _on_mode_change(self, mode):
        self.logger.info(f"Layout Shift: Applying {mode} workspace")
        self.layout.select_layout(mode)

    def _on_intent_change(self, data):
        intent = data.get("intent")
        self.dock.reorder_by_intent(intent)

    def _on_health_check(self, data):
        cpu = data.get("cpu", 0)
        if cpu > 85:
            self.layout.apply_minimal_profile()
