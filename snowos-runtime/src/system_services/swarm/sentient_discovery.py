import time
import socket
import logging
import json
import os

class SentientDiscovery:
    """Handles discovery and health tracking of SnowOS swarm peers."""
    
    def __init__(self):
        self.nodes = {} # {node_id: {health_data, last_seen}}
        self.logger = logging.getLogger("SnowOS.SwarmDiscovery")
        self.local_id = socket.gethostname()

    def broadcast_presence(self, health_data):
        """Broadcast local node health to the swarm (Stub)."""
        # In a real environment, this would be a UDP broadcast or mDNS update
        self.logger.debug(f"Swarm: Broadcasting presence for {self.local_id}")
        # Self-update
        self.nodes[self.local_id] = {
            "health": health_data,
            "last_seen": time.time(),
            "status": "online"
        }

    def get_available_peers(self):
        """Return list of healthy peers capable of taking tasks."""
        now = time.time()
        healthy = []
        for nid, data in self.nodes.items():
            if nid == self.local_id: continue
            if now - data["last_seen"] < 60: # Node is active
                if data["health"].get("cpu", 100) < 50: # Node has capacity
                    healthy.append(nid)
        return healthy

    def update_peer(self, node_id, health_data):
        """Update information about a discovered peer."""
        self.nodes[node_id] = {
            "health": health_data,
            "last_seen": time.time(),
            "status": "online"
        }
        self.logger.info(f"Swarm: Discovered/Updated peer {node_id}")
