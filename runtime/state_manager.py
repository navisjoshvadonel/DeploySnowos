import threading
import json
import os

class StateManager:
    """Maintains the global truth of the SnowOS environment."""
    
    def __init__(self, state_file=None):
        self.state_file = state_file or os.path.expanduser("~/.snowos/runtime/global_state.json")
        self.state = {
            "mode": "calm",           # calm, dev, performance
            "focus_app": "terminal",
            "system_load": "low",     # low, medium, high
            "user_state": "active",   # active, idle, focus
            "last_prediction": None,
            "ai_autonomy": "assistive" # manual, assistive, autonomous
        }
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.state.update(data)
            except Exception:
                pass

    def _save(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception:
            pass

    def update_state(self, key, value):
        """Thread-safe state update."""
        with self._lock:
            if key in self.state:
                old_value = self.state[key]
                if old_value != value:
                    self.state[key] = value
                    self._save()
                    return True, old_value
        return False, None

    def get_snapshot(self):
        """Return a copy of the current state."""
        with self._lock:
            return dict(self.state)
