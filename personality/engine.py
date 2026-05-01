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
        self.profile_path = os.path.expanduser("~/.snowos/personality/profiles.json")
        self.state_path = os.path.expanduser("~/.snowos/personality/state.json")
        self.logger = logging.getLogger("SnowOS.Personality")
        
        self.profiles = self._load_profiles()
        self.current_mode = self._load_state()

    def _load_profiles(self):
        try:
            with open(self.profile_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

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
