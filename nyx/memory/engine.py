import os
import json
import sys

# Ensure the memory directory is in path for imports
sys.path.append(os.path.dirname(__file__))

try:
    from logger import MemoryLogger
    from predictor import BehaviorPredictor
except ImportError:
    # Fallback for different execution contexts
    from .logger import MemoryLogger
    from .predictor import BehaviorPredictor

class NyxMemoryEngine:
    """The central intelligence engine for SnowOS Behavioral Learning."""
    
    def __init__(self):
        self.logger = MemoryLogger()
        self.predictor = BehaviorPredictor(self.logger)
        self.config_path = os.path.expanduser("~/.snowos/nyx/memory/config.json")
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {"prediction_threshold": 0.5, "max_history": 100}

    def log_event(self, command, action, status):
        """Asynchronously log an event to memory."""
        # For true async, we'd use a thread, but for SQLite simple inserts are fast enough
        self.logger.log_event(command, action, status)

    def get_suggestions(self):
        """Get predictive suggestions for the terminal or UI."""
        return self.predictor.get_suggestions()

    def get_frequent_apps(self):
        """Return a list of frequently used commands/apps for dock integration."""
        patterns = self.predictor.analyze_patterns()
        return [cmd for cmd, count in patterns["frequent_commands"]]

    def predict_next_action(self):
        """Predict the most likely next action."""
        patterns = self.predictor.analyze_patterns()
        return patterns["prediction"]
