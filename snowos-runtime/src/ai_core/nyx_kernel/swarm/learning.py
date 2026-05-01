import threading
import time
import json
from typing import List, Dict

class SwarmLearningSync:
    """
    Stage 41 — Shared Learning Layer.
    Synchronizes non-sensitive insights and patterns across the swarm.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _sync_loop(self):
        """Periodically share local insights with peers."""
        while not self._stop_event.is_set():
            time.sleep(600) # Sync every 10 minutes for high-speed autonomy
            self.share_insights()

    def broadcast_urgent(self, insight: Dict):
        """Immediately propagate a critical insight to the swarm."""
        peers = self.nyx.swarm_engine.get_active_peers()
        for p in peers:
            # Urgent call (async in a real system)
            self.nyx.swarm.call_node(p["node_id"], "/swarm/learn", {"insights": [insight]})

    def share_insights(self):
        """Pushes non-sensitive insights to trusted peers."""
        local_insights = self.nyx.reflection.insights
        if not local_insights:
            return
            
        # Filter sensitive data (simple heuristic: remove any fields with 'path', 'user', 'secret')
        safe_insights = []
        for ins in local_insights:
            safe_ins = {k: v for k, v in ins.items() if not any(s in k.lower() for s in ['path', 'user', 'secret'])}
            safe_insights.append(safe_ins)
            
        peers = self.nyx.swarm_engine.get_active_peers()
        for p in peers:
            self.nyx.swarm.call_node(p["node_id"], "/swarm/learn", {"insights": safe_insights})

    def ingest_remote_insights(self, insights: List[Dict]):
        """Ingests insights received from other nodes."""
        with self._lock:
            # Append to local reflection engine (or a separate swarm-knowledge store)
            # For now, we add them to the reflection insights with a 'swarm' tag
            for ins in insights:
                ins["source"] = "swarm"
                if ins not in self.nyx.reflection.insights:
                    self.nyx.reflection.insights.append(ins)
            self.nyx.reflection._save()
