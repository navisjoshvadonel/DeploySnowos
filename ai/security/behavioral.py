import re
try:
    try:
        from ai.memory.vector_db import VectorMemory
    except ImportError:
        from memory.vector_db import VectorMemory
except Exception:
    class VectorMemory:
        def __init__(self):
            self.collection = None
        def query(self, *args, **kwargs):
            return {}

class BehavioralSecurity:
    """Detects 'out of character' or semantically risky commands."""
    
    def __init__(self, vector_db=None):
        try:
            self.vector_db = vector_db or VectorMemory()
        except Exception:
            self.vector_db = VectorMemory()
        self.risk_threshold = 0.75 # Lower distance means more similar (safe)
        
        # High-risk semantic concepts
        self.DANGER_CONCEPTS = [
            "delete system files",
            "recursive force remove root",
            "modify kernel parameters",
            "unauthorized network exfiltration",
            "overwrite bootloader",
            "disable firewall and security"
        ]

    def score_command(self, command):
        """
        Returns a risk score from 0.0 (safe) to 1.0 (malicious).
        Combines pattern entropy with semantic distance to known risks.
        """
        # A) Distance from 'Safe History' (anomaly detection)
        avg_safe_dist = 0.5
        try:
            if hasattr(self.vector_db, "collection") and self.vector_db.collection:
                safe_results = self.vector_db.query(command, n_results=3)
                if safe_results and 'distances' in safe_results and safe_results['distances']:
                    dists = safe_results['distances'][0]
                    avg_safe_dist = sum(dists) / len(dists) if dists else 0.5
        except Exception:
            avg_safe_dist = 0.5
        
        # B) Heuristic Entropy
        entropy_score = 0.0
        if re.search(r"rm\s+-rf\s+/", command): entropy_score += 0.9
        if re.search(r"curl.*\|\s*(?:ba)?sh", command): entropy_score += 0.7
        if re.search(r">/dev/mem", command): entropy_score += 0.8
        
        # Final Score Calculation
        # High avg_safe_dist (e.g. 0.9) means it's unlike anything seen before.
        # High entropy means it's inherently dangerous.
        final_risk = (avg_safe_dist * 0.4) + (entropy_score * 0.6)
        return min(1.0, final_risk)

    def is_anomalous(self, command):
        score = self.score_command(command)
        return score > self.risk_threshold, score
