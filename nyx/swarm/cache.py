import threading
import time
import hashlib
import json
from typing import Any, Optional, Dict

class SwarmCache:
    """
    Stage 41 — Swarm Memory Cache.
    Distributed result caching for expensive task executions.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.cache: Dict[str, Dict] = {} # hash -> {result, expires, user_id}
        self._lock = threading.Lock()

    def _hash_task(self, task_description: str, context: dict = None) -> str:
        data = task_description + json.dumps(context or {}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, task_description: str, context: dict = None) -> Optional[Any]:
        """Check local cache for a result."""
        task_hash = self._hash_task(task_description, context)
        with self._lock:
            entry = self.cache.get(task_hash)
            if entry:
                if entry["expires"] > time.time():
                    return entry["result"]
                else:
                    del self.cache[task_hash]
        return None

    def set(self, task_description: str, result: Any, ttl: int = 3600, context: dict = None):
        """Store a result in the local cache."""
        task_hash = self._hash_task(task_description, context)
        with self._lock:
            self.cache[task_hash] = {
                "result": result,
                "expires": time.time() + ttl,
                "user_id": self.nyx.current_user["user_id"]
            }

    def query_swarm(self, task_description: str, context: dict = None) -> Optional[Any]:
        """Ask the swarm if anyone has the result cached."""
        task_hash = self._hash_task(task_description, context)
        peers = self.nyx.swarm_engine.get_active_peers()
        
        for p in peers:
            response = self.nyx.swarm.call_node(p["node_id"], "/swarm/cache/get", {"hash": task_hash})
            if "result" in response and response["result"] is not None:
                # Optional: Validate result hash or identity here
                return response["result"]
        return None
