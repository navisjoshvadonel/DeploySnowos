import logging
from execution.action_engine import ActionEngine

logger = logging.getLogger("SchedulerCore")

class SchedulerCore:
    def __init__(self):
        self.action_engine = ActionEngine()

    def process_predictions(self, predictions):
        """
        Translates AI predictions into concrete execution actions.
        """
        for pred in predictions:
            if pred["type"] == "throttle_recommendation":
                logger.info(f"Processing Throttle Recommendation: {pred['reason']}")
                self.action_engine.execute_throttle(pred["target_pid"], pred["target_name"])
                
            elif pred["type"] == "preload_recommendation":
                logger.info(f"Processing Preload Recommendation: {pred['reason']}")
                self.action_engine.execute_preload(pred["target_name"])
