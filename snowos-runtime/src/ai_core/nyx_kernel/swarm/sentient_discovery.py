import time
import socket
import logging
import json
import os

class SentientDiscovery:
    """Handles discovery and health tracking of SnowOS swarm peers."""
    
    def __init__(self, port=49152):
        self.nodes = {} # {node_id: {health_data, last_seen}}
        self.logger = logging.getLogger("SnowOS.SwarmDiscovery")
        self.local_id = socket.gethostname()
        self.port = port
        self.broadcast_ip = "255.255.255.255"
        
        # Setup socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(False)
        
        try:
            self.socket.bind(('', self.port))
            self.logger.info(f"Swarm: Discovery active on port {self.port}")
        except Exception as e:
            self.logger.error(f"Swarm: Failed to bind discovery socket: {e}")

    def broadcast_presence(self, health_data):
        """Broadcast local node health to the swarm."""
        message = json.dumps({
            "node_id": self.local_id,
            "health": health_data,
            "timestamp": time.time()
        }).encode()
        
        try:
            self.socket.sendto(message, (self.broadcast_ip, self.port))
            self.logger.debug(f"Swarm: Broadcasted presence to {self.broadcast_ip}")
        except Exception as e:
            self.logger.error(f"Swarm: Broadcast failed: {e}")

    def listen_for_peers(self):
        """Receive presence updates from other nodes."""
        while True:
            try:
                data, addr = self.socket.recvfrom(4096)
                payload = json.loads(data.decode())
                node_id = payload.get("node_id")
                if node_id and node_id != self.local_id:
                    self.update_peer(node_id, payload.get("health", {}))
            except (BlockingIOError, json.JSONDecodeError):
                break
            except Exception as e:
                self.logger.error(f"Swarm: Receive error: {e}")
                break

    def get_available_peers(self):
        """Return list of healthy peers capable of taking tasks."""
        self.listen_for_peers() # Check for fresh updates
        self._prune_dead_nodes()
        
        now = time.time()
        healthy = []
        for nid, data in self.nodes.items():
            if nid == self.local_id: continue
            if now - data["last_seen"] < 30: # Active within last 30s
                if data["health"].get("cpu", 100) < 60: # Capacity threshold
                    healthy.append(nid)
        return healthy

    def _prune_dead_nodes(self):
        """Remove nodes that haven't been seen in over 60 seconds."""
        now = time.time()
        to_delete = [nid for nid, data in self.nodes.items() if now - data["last_seen"] > 60]
        for nid in to_delete:
            del self.nodes[nid]
            self.logger.info(f"Swarm: Pruned offline node {nid}")

    def update_peer(self, node_id, health_data):
        """Update information about a discovered peer."""
        is_new = node_id not in self.nodes
        self.nodes[node_id] = {
            "health": health_data,
            "last_seen": time.time(),
            "status": "online"
        }
        if is_new:
            self.logger.info(f"Swarm: Discovered new peer {node_id}")

