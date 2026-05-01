import time
import random
from typing import Dict, Any

class ArchitectureSimulator:
    """
    Stage 42 — Architecture Simulation Engine.
    Simulates the impact of architectural changes before they are applied.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent

    def simulate_proposal(self, proposal: Dict) -> Dict[str, Any]:
        """
        Runs a simulation of a proposal and returns predicted metrics.
        Uses synthetic benchmarks and historical trace data.
        """
        print(f"[dim]🧪 Simulating proposal {proposal['id']}: {proposal['description']}[/dim]")
        
        # 1. Fetch current baseline metrics for affected modules
        affected = proposal.get("affected_modules", [])
        baseline = self._get_baseline_metrics(affected)
        
        # 2. Apply "virtual" changes based on proposal type
        ptype = proposal.get("type")
        predicted = baseline.copy()
        
        if ptype == "OPTIMIZATION":
            # Simulate caching: reduce latency, increase memory slightly
            predicted["latency"] *= 0.6
            predicted["mem"] *= 1.1
        elif ptype == "DISTRIBUTION":
            # Simulate swarm offloading: reduce local CPU, increase network latency
            predicted["cpu"] *= 0.5
            predicted["latency"] *= 1.2
        elif ptype == "REFACTOR":
            # Simulate decoupling: reduce failure rate, slightly increase latency
            predicted["failure_rate"] *= 0.7
            predicted["latency"] *= 1.05

        # 3. Validation Check
        is_safe = self._validate_simulation(predicted)
        
        return {
            "proposal_id": proposal["id"],
            "baseline": baseline,
            "predicted": predicted,
            "improvement_score": self._calculate_improvement(baseline, predicted),
            "is_safe": is_safe,
            "simulation_time": time.time()
        }

    def _get_baseline_metrics(self, modules: list) -> Dict[str, float]:
        # Aggregate metrics from the architecture graph
        graph = self.nyx.arch_profiler.graph
        metrics = {"latency": 0.0, "cpu": 0.0, "mem": 0.0, "failure_rate": 0.0}
        
        count = 0
        with graph._lock:
            for m in modules:
                if m in graph.nodes:
                    node = graph.nodes[m]
                    metrics["latency"] += node.latency_contribution
                    metrics["cpu"] += node.cpu_usage
                    metrics["mem"] += node.mem_usage
                    metrics["failure_rate"] += node.failure_rate
                    count += 1
        
        if count > 0:
            for k in metrics: metrics[k] /= count
            
        return metrics

    def _calculate_improvement(self, base: dict, pred: dict) -> float:
        # Simple weighted score of improvements
        # Lower is better for latency, cpu, mem, failure_rate
        improvement = 0.0
        for k in base:
            if base[k] > 0:
                improvement += (base[k] - pred[k]) / base[k]
        return improvement

    def _validate_simulation(self, predicted: dict) -> bool:
        # Safety rules: no extreme resource spikes
        if predicted["cpu"] > 95.0: return False
        if predicted["failure_rate"] > 0.5: return False
        return True
