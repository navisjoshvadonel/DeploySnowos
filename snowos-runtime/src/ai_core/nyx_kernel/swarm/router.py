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

    def route_task(self, task_description: str, strategy: str = RoutingStrategy.LEAST_LOADED) -> Tuple[str, str]:
        """
        Routes a task to the best node.
        Returns: (node_id, routing_reason)
        """
        peers = self.nyx.swarm_engine.get_active_peers()
        local_profile = self.nyx.profiler.get_profile()
        
        # Always include self as a candidate
        all_candidates = peers + [{"node_id": self.nyx.node_id, "profile": local_profile}]
        
        if strategy == RoutingStrategy.LOCAL_ONLY or not peers:
            return self.nyx.node_id, "Strategy: Local Only or no peers available"

        if strategy == RoutingStrategy.LEAST_LOADED:
            return self._least_loaded_route(all_candidates)
        elif strategy == RoutingStrategy.FASTEST:
            return self._fastest_route(all_candidates)
        
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
