import logging

class ActionGating:
    """The final safety check before SnowOS takes autonomous action."""
    
    def __init__(self, personality_engine, trust_engine):
        self.persona = personality_engine
        self.trust = trust_engine
        self.logger = logging.getLogger("SnowOS.Gating")

    def validate_action(self, action_name):
        """Returns (is_allowed, reason)."""
        config = self.persona.get_current_config()
        analysis = self.trust.analyze_prediction(action_name)
        
        # 1. Mode Check
        if not config or not config.get("auto_action", False):
            return False, f"Current mode '{self.persona.current_mode}' requires manual confirmation."

        # 2. Destructive Action Check
        destructive = ["rm -rf", "mkfs", "dd"]
        if any(d in action_name for d in destructive):
            return False, "Security block: Destructive command detected. Manual override required."

        # 3. Confidence Check
        threshold = config.get("confidence_threshold", 0.85)
        if analysis["confidence"] < threshold:
            return False, f"Confidence ({analysis['confidence']}) below required threshold ({threshold})."

        return True, "Gating cleared: High confidence autonomous action allowed."
