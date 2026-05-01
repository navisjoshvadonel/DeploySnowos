import threading
import time
from typing import Dict, List
from .model import ArchitectureGraph

class ArchitectureProfiler:
    """
    Stage 42 — Architecture Profiler.
    Continuously analyzes system telemetry to detect bottlenecks and coupling.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.graph = ArchitectureGraph()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._profiling_loop, daemon=True)
        
        # Initialize default nodes
        self._init_default_nodes()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _init_default_nodes(self):
        core_modules = [
            "NyxAI", "GoalEngine", "TaskScheduler", "APIServer", 
            "KernelMonitor", "SwarmEngine", "ReflectionEngine", "Sandbox",
            "UIEngine"
        ]
        for m in core_modules:
            self.graph.add_node(m, "core_module")

    def _profiling_loop(self):
        while not self._stop_event.is_set():
            self._update_from_telemetry()
            self._update_from_kernel()
            self._analyze_coupling()
            self._stop_event.wait(60) # Profile every minute

    def _update_from_telemetry(self):
        """Pull spans and metrics from Telemetry to update graph edges/nodes."""
        # Query recent spans from observability storage
        recent_spans = self.nyx.telemetry.storage.get_recent_spans(limit=500)
        
        for span in recent_spans:
            name = span["name"]
            stype = span["type"]
            latency = (span["end_time"] - span["start_time"]) if span["end_time"] else 0
            
            # Map span types to nodes/edges
            # Example: remote_call: endpoint -> SwarmEngine -> Peer
            if name.startswith("remote_call:"):
                self.graph.add_edge("SwarmEngine", "RemoteNode", "network_call")
                self.graph.update_edge_metrics("SwarmEngine", "RemoteNode", latency)
            elif stype == "api":
                self.graph.add_edge("APIServer", "NyxAI", "request_routing")
                self.graph.update_node_metrics("APIServer", latency_contribution=latency)

    def _update_from_kernel(self):
        """Pull resource metrics from KernelMonitor."""
        # For each core module, we try to map it to processes or resource groups
        # Here we use simplified mapping for the OS model
        local_load = self.nyx.profiler.get_profile()
        self.graph.update_node_metrics("NyxAI", cpu_usage=local_load.get("current_load", 0))

    def _analyze_coupling(self):
        """Analyze frequency of interactions to estimate coupling level."""
        with self.graph._lock:
            for node_name in self.graph.nodes:
                # Count edges connected to this node
                coupling_count = sum(1 for e in self.graph.edges if e.source == node_name or e.target == node_name)
                # Normalize coupling (simple heuristic)
                coupling_level = min(1.0, coupling_count / 10.0)
                self.graph.nodes[node_name].coupling_level = coupling_level

    def get_bottlenecks(self, latency_threshold=2.0) -> List[Dict]:
        """Identify nodes with high latency or resource usage."""
        bottlenecks = []
        with self.graph._lock:
            for name, node in self.graph.nodes.items():
                if node.latency_contribution > latency_threshold or node.cpu_usage > 80.0:
                    bottlenecks.append({
                        "name": name,
                        "latency": node.latency_contribution,
                        "cpu": node.cpu_usage,
                        "reason": "High Latency" if node.latency_contribution > latency_threshold else "High CPU"
                    })
        return bottlenecks
