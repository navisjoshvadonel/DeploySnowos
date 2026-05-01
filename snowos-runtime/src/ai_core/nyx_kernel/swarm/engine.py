import threading
import time
import requests
from typing import Dict, List, Optional
from .profiler import NodeProfiler

class SwarmEngine:
    """
    Stage 41 — Swarm Coordination Engine.
    Manages peer discovery, heartbeat monitoring, and distributed state.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.peers: Dict[str, Dict] = {} # node_id -> {url, profile, status, last_seen}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._maintenance_loop, daemon=True)

    def start(self):
        # Initial load from NodeStore
        self._sync_from_store()
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _sync_from_store(self):
        """Load trusted nodes from the NodeStore."""
        nodes = self.nyx.node_manager.get_nodes()
        with self._lock:
            for n in nodes:
                if n["trust_status"] == "trusted":
                    self.peers[n["node_id"]] = {
                        "url": n["url"],
                        "profile": {},
                        "status": "unknown",
                        "last_seen": n["last_seen"]
                    }

    def _maintenance_loop(self):
        """Periodic heartbeats and profile updates."""
        while not self._stop_event.is_set():
            self._check_peers()
            time.sleep(30)

    def _check_peers(self):
        """Send heartbeats and fetch profiles from peers."""
        # Sync from store in case new nodes were added
        self._sync_from_store()
        
        peer_ids = list(self.peers.keys())
        for pid in peer_ids:
            if pid == self.nyx.node_id:
                continue # Skip self
                
            threading.Thread(target=self._ping_peer, args=(pid,), daemon=True).start()

    def _ping_peer(self, node_id: str):
        """Ping a specific peer and update its status."""
        try:
            # Stage 41 Endpoint: /swarm/profile
            response = self.nyx.swarm.call_node(node_id, "/swarm/profile")
            with self._lock:
                if "error" not in response:
                    self.peers[node_id]["status"] = "online"
                    self.peers[node_id]["profile"] = response
                    self.peers[node_id]["last_seen"] = time.time()
                else:
                    self.peers[node_id]["status"] = "offline"
        except Exception:
            with self._lock:
                self.peers[node_id]["status"] = "offline"

    def get_active_peers(self) -> List[Dict]:
        """Returns a list of online peers with their profiles."""
        with self._lock:
            return [
                {"node_id": nid, **data}
                for nid, data in self.peers.items()
                if data["status"] == "online"
            ]

    def get_node_profile(self, node_id: str) -> Optional[Dict]:
        """Returns the profile of a specific node."""
        with self._lock:
            if node_id == self.nyx.node_id:
                return self.nyx.profiler.get_profile()
            return self.peers.get(node_id, {}).get("profile")
