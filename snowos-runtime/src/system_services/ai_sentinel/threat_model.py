import time
from collections import defaultdict

class ThreatModel:
    def __init__(self):
        # Maps source_id -> list of timestamps
        self.request_history = defaultdict(list)
        self.VELOCITY_THRESHOLD = 5 # max requests per second
        
    def evaluate(self, payload):
        """
        Evaluate if a payload is anomalous.
        Returns a risk score from 0.0 (safe) to 1.0 (malicious).
        """
        source = payload.get("source_id", "unknown")
        action = payload.get("action", "")
        target = payload.get("target_resource", "")
        
        current_time = time.time()
        
        # 1. Clean up old history (older than 1 second)
        self.request_history[source] = [t for t in self.request_history[source] if current_time - t < 1.0]
        
        # 2. Record new request
        self.request_history[source].append(current_time)
        
        # 3. Check Velocity Anomaly
        requests_last_sec = len(self.request_history[source])
        if requests_last_sec > self.VELOCITY_THRESHOLD:
            # Velocity exceeds threshold, high risk
            return 0.9
            
        # 4. Contextual Mismatch Check (Simple Heuristic)
        context = payload.get("context", "")
        if "delete" in action.lower() and "sync" in context.lower():
            # Suspicious combination: syncing shouldn't aggressively delete
            return 0.6
            
        # Safe
        return 0.1
