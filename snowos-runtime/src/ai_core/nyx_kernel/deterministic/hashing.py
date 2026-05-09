import hashlib
import json

class PlanHashingEngine:
    @staticmethod
    def generate_plan_id(goal, plan, context=None):
        """
        Deterministically generate a unique plan_id from goal, plan, and context.
        Uses canonical JSON serialization (sorted keys).
        """
        payload = {
            "goal": goal.strip(),
            "plan": plan,
            "context": context or {}
        }
        
        # Canonical JSON: sorted keys and separators without whitespace
        canonical_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # SHA-256 hash
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
