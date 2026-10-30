import json
import os
import logging
import sys

# Ensure parent dirs are in path for runtime imports
sys.path.append(os.path.expanduser("~/.snowos"))

try:
    from runtime.event_bus import bus
except ImportError:
    class MockBus:
        def publish(self, *args): pass
    bus = MockBus()

class PersonalityEngine:
    """Manages the behavioral persona of SnowOS."""
    
    def __init__(self):
        self.profile_path = os.environ.get("SNOWOS_PROFILES_PATH") or os.path.expanduser("~/.snowos/personality/profiles.json")
        self.state_path = os.environ.get("SNOWOS_STATE_PATH") or os.path.expanduser("~/.snowos/personality/state.json")
        self.logger = logging.getLogger("SnowOS.Personality")
        
        self.profiles = self._load_profiles()
        self.current_mode = self._load_state()

    def _load_profiles(self):
        # 1. Try specified or home path
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # 2. Try adjacent profiles.json
        local_path = os.path.join(os.path.dirname(__file__), "profiles.json")
        if os.path.exists(local_path):
            try:
                with open(local_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

        # 3. Built-in resilient fallback
        return {
            "calm": {"suggestion_level": "low", "auto_action": False, "ui_movement": "minimal", "confidence_threshold": 0.95},
            "assistive": {"suggestion_level": "medium", "auto_action": False, "ui_movement": "moderate", "confidence_threshold": 0.85},
            "autonomous": {"suggestion_level": "high", "auto_action": True, "ui_movement": "dynamic", "confidence_threshold": 0.80},
            "developer": {"suggestion_level": "low", "auto_action": False, "ui_movement": "none", "confidence_threshold": 0.99}
        }

    def _load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r') as f:
                    return json.load(f).get("mode", "assistive")
            except Exception:
                pass
        return "assistive"

    def _save_state(self):
        try:
            with open(self.state_path, 'w') as f:
                json.dump({"mode": self.current_mode}, f)
        except Exception:
            pass

    def set_mode(self, mode):
        """Change the OS personality mode."""
        if mode in self.profiles:
            self.current_mode = mode
            self._save_state()
            self.logger.info(f"Personality shifted to: {mode}")
            
            # Broadcast to Runtime and UI
            bus.publish("personality_change", {
                "mode": mode,
                "config": self.profiles[mode]
            })
            return True
        return False

    def get_current_config(self):
        """Return config for the active mode."""
        return self.profiles.get(self.current_mode, self.profiles.get("assistive"))

    def get_mode_name(self):
        return self.current_mode
