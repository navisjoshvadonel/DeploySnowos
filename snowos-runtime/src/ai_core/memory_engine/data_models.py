from dataclasses import dataclass
from typing import List, Optional

@dataclass
class UserBehavior:
    pattern_id: str
    context: str
    sequence: List[str]
    confidence: float

@dataclass
class SystemDecision:
    decision_id: str
    action: str
    target: str
    outcome: str # "success", "user_reverted", "failed"
    confidence_delta: float

@dataclass
class AnomalyRecord:
    anomaly_id: str
    source: str
    description: str
    severity: str
