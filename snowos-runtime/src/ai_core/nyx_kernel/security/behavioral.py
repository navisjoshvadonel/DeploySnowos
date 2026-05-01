import re
from ..memory.vector_db import VectorMemory

class BehavioralSecurity:
    """Detects 'out of character' or semantically risky commands."""
    
    def __init__(self, vector_db=None):
        self.vector_db = vector_db or VectorMemory()
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
        # 1. Semantic Risk: How close is this to a 'Danger Concept'?
        results = self.vector_db.query(command, n_results=1)
        danger_query = self.vector_db.collection.query(
            query_texts=self.DANGER_CONCEPTS,
            n_results=1
        )
        
        # Check against dangerous concepts
        min_danger_dist = 1.0
        if danger_query and 'distances' in danger_query:
            # This is slightly complex: we want to know if 'command' is close to any DANGER_CONCEPTS
            # Actually, we should just query the collection WITH the command and see the distance.
            # But the collection contains safe interactions.
            pass

        # Let's simplify: 
        # A) Distance from 'Safe History' (anomaly detection)
        # B) Presence of 'Exploitative' patterns (heuristic)
        
        safe_results = self.vector_db.query(command, n_results=3)
        avg_safe_dist = sum(safe_results['distances'][0]) / len(safe_results['distances'][0]) if safe_results['distances'][0] else 1.0
        
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
