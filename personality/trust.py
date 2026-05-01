import time
import logging

class TrustEngine:
    """Provides explainability and confidence scoring for OS decisions."""
    
    def __init__(self, memory_engine=None):
        self.memory = memory_engine
        self.logger = logging.getLogger("SnowOS.Trust")
        self.last_analysis = None

    def analyze_prediction(self, prediction):
        """Generate a confidence score and reason for a prediction."""
        if not self.memory:
            return {"confidence": 0.5, "reason": "Memory engine offline."}

        # Analysis based on history
        history = self.memory.logger.get_recent_history(limit=50)
        occurrences = sum(1 for row in history if row[1] == prediction)
        
        # Heuristic confidence
        # More occurrences = higher confidence
        confidence = min(0.95, (occurrences / 8.0)) 
        
        # Reason generation
        if occurrences > 0:
            reason = f"Detected {occurrences} similar actions in recent history."
        else:
            reason = "Emerging pattern detected in system telemetry."

        if occurrences > 5:
            reason += " This is a highly repetitive task."

        self.last_analysis = {
            "prediction": prediction,
            "confidence": round(confidence, 2),
            "reason": reason,
            "timestamp": time.time()
        }
        return self.last_analysis

    def get_last_explanation(self):
        """Return the reasoning for the most recent system insight."""
        if self.last_analysis:
            return self.last_analysis
        return {"reason": "No recent actions to explain."}
