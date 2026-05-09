import json
import os
import time
import logging

class FeedbackSystem:
    """Captures user feedback to tune OS behavior."""
    
    def __init__(self):
        self.log_path = os.path.expanduser("~/.snowos/personality/feedback.json")
        self.logger = logging.getLogger("SnowOS.Feedback")

    def submit(self, sentiment, comment=""):
        """Log user feedback (good/bad)."""
        entry = {
            "timestamp": time.time(),
            "sentiment": sentiment, # "good" or "bad"
            "comment": comment
        }
        
        try:
            history = []
            if os.path.exists(self.log_path):
                with open(self.log_path, 'r') as f:
                    history = json.load(f)
            
            history.append(entry)
            with open(self.log_path, 'w') as f:
                json.dump(history, f, indent=2)
            
            self.logger.info(f"User feedback logged: {sentiment}")
            
            # Publish for real-time adaptation
            from runtime.event_bus import bus
            bus.publish("user_feedback", entry)
            return True
        except Exception as e:
            self.logger.error(f"Failed to log feedback: {e}")
            return False

    def get_summary(self):
        """Calculate recent satisfaction score."""
        if not os.path.exists(self.log_path):
            return 1.0
        try:
            with open(self.log_path, 'r') as f:
                history = json.load(f)
            if not history: return 1.0
            
            recent = history[-20:]
            good = sum(1 for e in recent if e["sentiment"] == "good")
            return good / len(recent)
        except Exception:
            return 1.0
