import os
import random
from typing import Dict, List, Optional, Tuple

class RoutingStrategy:
    LEAST_LOADED = "least_loaded"
    FASTEST = "fastest"
    RESOURCE_FIT = "resource_fit"
    LOCAL_ONLY = "local_only"

class TaskRouter:
    """
    Stage 41 — Intelligent Task Router.
    Decides whether to execute a task locally or remotely, and selects the optimal node.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent

    def _get_thermal_load(self) -> float:
        """Returns the thermal temperature in Celsius, or 0.0 if unknown."""
        try:
            temp_path = "/sys/class/thermal/thermal_zone0/temp"
            if os.path.exists(temp_path):
                with open(temp_path, "r") as f:
                    return float(f.read().strip()) / 1000.0
        except Exception:
            pass
        return 0.0

    def route_task(self, task_description: str, strategy: str = RoutingStrategy.LEAST_LOADED) -> Tuple[str, str]:
        """
        Routes a task to the best node.
        Returns: (node_id, routing_reason)
        """
        peers = self.nyx.swarm_engine.get_active_peers()
        local_profile = self.nyx.profiler.get_profile()
        
        # Dynamic Swarm Thermal Offloading Governor
        local_temp = self._get_thermal_load()
        if local_temp > 85.0 and peers:
            # Extreme thermal penalty: Force remote offloading to preserve local thermals
            local_profile["current_load"] = 999.0
            strategy = RoutingStrategy.LEAST_LOADED
        
        # Always include self as a candidate
        all_candidates = peers + [{"node_id": self.nyx.node_id, "profile": local_profile}]
        
        if strategy == RoutingStrategy.LOCAL_ONLY or not peers:
            return self.nyx.node_id, "Strategy: Local Only or no peers available"

        reason_prefix = f"Thermal Offload ({local_temp:.1f}°C) - " if local_temp > 85.0 and peers else ""

        if strategy == RoutingStrategy.LEAST_LOADED:
            node, reason = self._least_loaded_route(all_candidates)
            return node, reason_prefix + reason
        elif strategy == RoutingStrategy.FASTEST:
            node, reason = self._fastest_route(all_candidates)
            return node, reason_prefix + reason
        
        # Default to local if unsure
        return self.nyx.node_id, "Fallback: Local"

    def _least_loaded_route(self, candidates: List[Dict]) -> Tuple[str, str]:
        """Select node with the lowest current load."""
        best_node = None
        min_load = 101.0
        
        for c in candidates:
            profile = c.get("profile", {})
            load = profile.get("current_load", 100.0)
            if load < min_load:
                min_load = load
                best_node = c["node_id"]
        
        reason = f"Least loaded node (Load: {min_load}%)"
        return best_node, reason

    def _fastest_route(self, candidates: List[Dict]) -> Tuple[str, str]:
        """Select node with the lowest historical latency."""
        best_node = None
        min_latency = float('inf')
        
        for c in candidates:
            profile = c.get("profile", {})
            latency = profile.get("avg_latency", float('inf'))
            if latency < min_latency:
                min_latency = latency
                best_node = c["node_id"]
        
        if not best_node:
            return self._least_loaded_route(candidates)
            
        reason = f"Fastest historical execution (Avg Latency: {min_latency:.2f}s)"
        return best_node, reason

    def should_decompose(self, task_description: str) -> bool:
        """
        Decide if a task is large enough to be split across the swarm.
        Currently uses simple keyword heuristics or AI intent.
        """
        large_task_keywords = ["setup full", "analyze all", "rebuild", "deploy cluster"]
        return any(k in task_description.lower() for k in large_task_keywords)

    def decompose_for_swarm(self, task_description: str) -> List[Dict]:
        """
        Decomposes a goal into sub-tasks for different nodes.
        Returns a list of task objects with node assignments.
        """
        subgoals = self.nyx.decompose_task(task_description)
        peers = self.nyx.swarm_engine.get_active_peers()
        all_nodes = [self.nyx.node_id] + [p["node_id"] for p in peers]
        
        assignments = []
        for i, sub in enumerate(subgoals):
            # Simple round-robin for decomposition
            target_node = all_nodes[i % len(all_nodes)]
            assignments.append({
                "goal": sub,
                "node_id": target_node
            })
        return assignments
