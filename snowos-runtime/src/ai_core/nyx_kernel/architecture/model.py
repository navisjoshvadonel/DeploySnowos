import threading
import time
import json
from typing import Dict, List, Any, Optional

class ArchitectureNode:
    """Represents a component/module in the SnowOS architecture."""
    def __init__(self, name: str, node_type: str):
        self.name = name
        self.type = node_type
        self.latency_contribution = 0.0
        self.cpu_usage = 0.0
        self.mem_usage = 0.0
        self.failure_rate = 0.0
        self.coupling_level = 0.0 # 0.0 (decoupled) to 1.0 (tightly coupled)
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)

class ArchitectureEdge:
    """Represents a dependency or interaction between components."""
    def __init__(self, source: str, target: str, interaction_type: str):
        self.source = source
        self.target = target
        self.type = interaction_type
        self.frequency = 0
        self.avg_latency = 0.0
        self.last_seen = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)

class ArchitectureGraph:
    """
    Stage 42 — Architecture Graph Model.
    Tracks SnowOS modules, their dependencies, and real-time performance metrics.
    """
    def __init__(self):
        self.nodes: Dict[str, ArchitectureNode] = {}
        self.edges: List[ArchitectureEdge] = []
        self._lock = threading.Lock()

    def add_node(self, name: str, node_type: str = "module"):
        with self._lock:
            if name not in self.nodes:
                self.nodes[name] = ArchitectureNode(name, node_type)

    def add_edge(self, source: str, target: str, interaction_type: str = "dependency"):
        with self._lock:
            # Ensure nodes exist
            if source not in self.nodes: self.nodes[source] = ArchitectureNode(source, "module")
            if target not in self.nodes: self.nodes[target] = ArchitectureNode(target, "module")
            
            # Check for existing edge
            for e in self.edges:
                if e.source == source and e.target == target:
                    e.frequency += 1
                    e.last_seen = time.time()
                    return
            
            self.edges.append(ArchitectureEdge(source, target, interaction_type))

    def update_node_metrics(self, name: str, **metrics):
        with self._lock:
            if name in self.nodes:
                node = self.nodes[name]
                for k, v in metrics.items():
                    if hasattr(node, k):
                        setattr(node, k, v)
                node.last_updated = time.time()

    def update_edge_metrics(self, source: str, target: str, latency: float):
        with self._lock:
            for e in self.edges:
                if e.source == source and e.target == target:
                    # Rolling average
                    e.avg_latency = (e.avg_latency * 0.9) + (latency * 0.1)
                    e.frequency += 1
                    e.last_seen = time.time()

    def get_graph_snapshot(self) -> Dict[str, Any]:
        """Returns a JSON-serializable snapshot of the graph."""
        with self._lock:
            return {
                "nodes": {name: node.to_dict() for name, node in self.nodes.items()},
                "edges": [edge.to_dict() for edge in self.edges],
                "timestamp": time.time()
            }
