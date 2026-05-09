import logging
from memory_engine.memory_store import MemoryStore

logger = logging.getLogger("FeedbackLoop")

class FeedbackLoop:
    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store

    def process_outcome(self, decision_id, outcome):
        """
        Adjusts confidence scores based on the outcome of an action.
        """
        logger.info(f"Processing outcome for decision {decision_id}: {outcome}")
        
        # In a real model, this would backpropagate or update weights.
        # Here we simulate adjusting a confidence multiplier.
        if outcome == "success":
            # Action was helpful, user didn't override. Boost confidence.
            new_confidence = min(0.99, self.memory.get_historical_confidence("", "") + 0.1)
        elif outcome == "user_reverted":
            # User hated it. Drop confidence heavily.
            new_confidence = max(0.1, self.memory.get_historical_confidence("", "") - 0.3)
        else:
            new_confidence = 0.5
            
        self.memory.update_outcome(decision_id, outcome, new_confidence)
        logger.info(f"Updated model weights. New baseline confidence: {new_confidence:.2f}")
        return new_confidence
