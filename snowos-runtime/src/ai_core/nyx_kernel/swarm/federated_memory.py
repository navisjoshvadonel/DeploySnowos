import logging
import time

class FederatedMemory:
    """Synchronizes collective intelligence across swarm nodes."""
    
    def __init__(self, memory_engine, task_broker):
        self.memory = memory_engine
        self.broker = task_broker
        self.logger = logging.getLogger("SnowOS.FederatedMemory")

    def sync_knowledge(self):
        """Broadcast high-confidence knowledge to all peers."""
        peers = self.broker.discovery.get_available_peers()
        if not peers: return

        # Retrieve successful patterns from local memory
        history = self.memory.logger.get_recent_history(limit=50)
        top_patterns = [h[1] for h in history if h[3] == "success"]
        
        if not top_patterns: return

        for peer in peers:
            self.logger.info(f"Swarm: Syncing federated memory with {peer}")
            self.broker.dispatch(peer, "knowledge_sync", {
                "patterns": list(set(top_patterns)),
                "source": self.broker.discovery.local_id
            })

    def ingest_remote_memory(self, data):
        """Integrate shared knowledge from another node."""
        source = data.get("source")
        patterns = data.get("patterns", [])
        
        self.logger.info(f"Swarm: Ingesting {len(patterns)} patterns from {source}")
        # Add to local learning cache
        for p in patterns:
            # We log as 'remote_success' to distinguish from local behavior
            self.memory.logger.log_event(p, "swarm_knowledge", "remote_success")
