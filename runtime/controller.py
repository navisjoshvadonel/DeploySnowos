import logging
from .event_bus import bus

class RuntimeController:
    """The 'Sentient Brain' that decides OS behavior based on events."""
    
    def __init__(self, state_manager):
        self.state = state_manager
        self.logger = logging.getLogger("SnowOS.Controller")
        self._setup_listeners()

    def _setup_listeners(self):
        # System health routing
        bus.subscribe("system_health", self._on_health_event)
        
        # User activity routing
        bus.subscribe("user_intent", self._on_user_intent)
        bus.subscribe("app_lifecycle", self._on_app_event)
        
        # AI Intelligence routing
        bus.subscribe("ai_insight", self._on_ai_insight)

    def _on_health_event(self, data):
        cpu = data.get("cpu", 0)
        if cpu > 80:
            changed, _ = self.state.update_state("system_load", "high")
            if changed:
                self._apply_performance_rules("high")
        elif cpu < 30:
            changed, _ = self.state.update_state("system_load", "low")
            if changed:
                self._apply_performance_rules("low")

    def _on_user_intent(self, data):
        intent = data.get("intent")
        self.logger.info(f"User intent shifted to: {intent}")
        if intent == "coding":
            self.state.update_state("mode", "dev")
            bus.publish("ui_mode_change", "dev")
        elif intent == "idle":
            self.state.update_state("mode", "calm")
            bus.publish("ui_mode_change", "calm")

    def _on_app_event(self, data):
        app = data.get("name")
        event = data.get("event") # opened, closed
        if event == "opened":
            self.state.update_state("focus_app", app)

    def _on_ai_insight(self, data):
        prediction = data.get("prediction")
        self.state.update_state("last_prediction", prediction)
        
        # Stage 70: Trust & Safety Gating
        if hasattr(self.nyx, "gating"):
            allowed, reason = self.nyx.gating.validate_action(prediction)
            if allowed:
                self.logger.info(f"Autonomously acting on prediction: {prediction}")
                bus.publish("action_trigger", {"action": prediction, "source": "autonomy"})
            else:
                self.logger.info(f"Autonomous action deferred: {reason}")
        else:
            # Fallback if gating not initialized
            autonomy = self.state.get_snapshot()["ai_autonomy"]
            if autonomy == "autonomous":
                bus.publish("action_trigger", {"action": prediction, "source": "autonomy"})

    def _apply_performance_rules(self, load_level):
        if load_level == "high":
            self.logger.warning("Applying High-Performance mode (throttling UI effects)")
            bus.publish("ui_mode_change", "performance")
            bus.publish("background_tasks", "pause")
        else:
            self.logger.info("Restoring normal mode")
            bus.publish("ui_mode_change", self.state.get("mode"))
            bus.publish("background_tasks", "resume")
