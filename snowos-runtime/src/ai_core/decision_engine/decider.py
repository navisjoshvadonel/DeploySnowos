import logging
import uuid
from memory_engine.memory_store import MemoryStore

logger = logging.getLogger("DecisionEngine")

class DecisionEngine:
    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store

    def evaluate_action(self, action, target):
        """
        Checks historical confidence before allowing the Predictive Optimizer
        or AI Core to execute an autonomous action.
        """
        confidence = self.memory.get_historical_confidence(action, target)
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Evaluating '{action}' on '{target}'. Historical confidence: {confidence:.2f}")
        
        # Log the pending decision to persistent memory
        self.memory.log_decision(decision_id, action, target, confidence)
        
        if confidence >= 0.70:
            logger.info(f"[{decision_id}] Confidence HIGH. Action auto-approved.")
            return {"decision_id": decision_id, "status": "APPROVED", "confidence": confidence}
        else:
            logger.warning(f"[{decision_id}] Confidence LOW ({confidence:.2f}). Deferring to SnowControl Intent Approval.")
            return {"decision_id": decision_id, "status": "REQUIRE_USER_APPROVAL", "confidence": confidence}
