import uuid
import time
from typing import List, Dict, Any

class DesignAnalysisEngine:
    """
    Stage 42 — Design Analysis Engine.
    Generates structured findings based on architectural patterns and bottlenecks.
    """
    def __init__(self, arch_profiler):
        self.profiler = arch_profiler

    def generate_findings(self) -> List[Dict[str, Any]]:
        findings = []
        bottlenecks = self.profiler.get_bottlenecks()
        
        for b in bottlenecks:
            findings.append({
                "id": str(uuid.uuid4())[:8],
                "component": b["name"],
                "finding": b["reason"],
                "severity": "HIGH" if b["cpu"] > 90 or b["latency"] > 5 else "MEDIUM",
                "impact_score": (b["cpu"] / 100.0) + (b["latency"] / 10.0),
                "timestamp": time.time()
            })
            
        # Check for tight coupling
        with self.profiler.graph._lock:
            for name, node in self.profiler.graph.nodes.items():
                if node.coupling_level > 0.8:
                    findings.append({
                        "id": str(uuid.uuid4())[:8],
                        "component": name,
                        "finding": "Tight Coupling Detected",
                        "severity": "MEDIUM",
                        "impact_score": 0.5,
                        "timestamp": time.time()
                    })
                    
        return findings

class RefactorProposalEngine:
    """
    Stage 42 — Refactor Proposal Engine.
    Suggests architectural changes to solve findings.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent

    def generate_proposals(self, findings: List[Dict]) -> List[Dict[str, Any]]:
        proposals = []
        for f in findings:
            proposal = self._create_proposal_for_finding(f)
            if proposal:
                proposals.append(proposal)
        return proposals

    def _create_proposal_for_finding(self, finding: Dict) -> Dict:
        comp = finding["component"]
        f_text = finding["finding"]
        
        proposal_id = "prop_" + str(uuid.uuid4())[:8]
        
        if "High Latency" in f_text:
            return {
                "id": proposal_id,
                "type": "OPTIMIZATION",
                "description": f"Introduce caching layer for {comp} to reduce latency.",
                "expected_improvement": "30-50% reduction in latency",
                "risk_level": "LOW",
                "affected_modules": [comp, "CacheManager"],
                "finding_id": finding["id"]
            }
        elif "Tight Coupling" in f_text:
            return {
                "id": proposal_id,
                "type": "REFACTOR",
                "description": f"Decouple {comp} by introducing an event-based interface.",
                "expected_improvement": "Reduced maintenance complexity and failure propagation",
                "risk_level": "MEDIUM",
                "affected_modules": [comp],
                "finding_id": finding["id"]
            }
        elif "High CPU" in f_text:
            return {
                "id": proposal_id,
                "type": "DISTRIBUTION",
                "description": f"Offload heavy tasks from {comp} to the Swarm.",
                "expected_improvement": "Balanced cluster load and local CPU headroom",
                "risk_level": "MEDIUM",
                "affected_modules": [comp, "SwarmEngine"],
                "finding_id": finding["id"]
            }
            
        return None
