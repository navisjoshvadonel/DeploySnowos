import logging
import os
import json

class LearningFeedbackLoop:
    """Closes the loop between user feedback and AI behavior."""
    
    def __init__(self, memory_engine):
        self.memory = memory_engine
        self.logger = logging.getLogger("SnowOS.LearningFeedback")

    def ingest_feedback(self, data):
        """Processes a 'user_feedback' event from the bus."""
        sentiment = data.get("sentiment")
        comment = data.get("comment")
        
        # If feedback is negative, we create a negative memory entry 
        # to discourage similar predictions.
        if sentiment == "bad":
            self.logger.warning(f"Negative feedback received. Adjusting weights for: {comment}")
            self.memory.logger.log_event(
                command=f"REJECTED_PATTERN: {comment}",
                action="learning_adjustment",
                status="failure"
            )
        else:
            self.logger.info("Positive feedback reinforces current patterns.")
            self.memory.logger.log_event(
                command=f"REINFORCED_PATTERN: {comment}",
                action="learning_adjustment",
                status="success"
            )

    def get_adjustment_score(self, command):
        """Returns a multiplier for confidence based on feedback history."""
        # Simple implementation: check for rejected patterns
        history = self.memory.logger.get_recent_history(limit=50)
        penalty = 0.0
        for h in history:
            if h[3] == "failure" and "REJECTED_PATTERN" in h[1]:
                if command in h[1]:
                    penalty += 0.2
        return max(0.1, 1.0 - penalty)
