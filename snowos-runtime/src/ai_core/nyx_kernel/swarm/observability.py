from typing import Dict, List, Any

class SwarmObservability:
    """
    Stage 41 — Swarm Observability.
    Provides cluster-wide visibility, topology, and performance heatmaps.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent

    def get_topology(self) -> Dict[str, Any]:
        """Returns the current swarm topology."""
        local_node = {
            "node_id": self.nyx.node_id,
            "status": "online",
            "is_local": True,
            "profile": self.nyx.profiler.get_profile()
        }
        
        peers = self.nyx.swarm_engine.get_active_peers()
        topology = {
            "nodes": [local_node] + peers,
            "active_tasks": self.nyx.swarm_executor.list_active_jobs()
        }
        return topology

    def get_load_heatmap(self) -> List[Dict[str, Any]]:
        """Returns CPU/Memory load data for all nodes."""
        nodes = [self.nyx.profiler.get_profile()]
        peers = self.nyx.swarm_engine.get_active_peers()
        
        heatmap = []
        for n in nodes + [p["profile"] for p in peers if "profile" in p]:
            heatmap.append({
                "node_id": n.get("node_id"),
                "cpu": n.get("current_load", 0),
                "mem": n.get("mem_used", 0)
            })
        return heatmap

    def get_contribution_stats(self) -> Dict[str, int]:
        """Tracks how many tasks each node has handled."""
        # This would ideally query the observability DB
        # For now, we'll return a simple summary from the active executor
        stats = {}
        for job in self.nyx.swarm_executor.list_active_jobs():
            for st in job["subtasks"]:
                nid = st["node_id"]
                stats[nid] = stats.get(nid, 0) + 1
        return stats
