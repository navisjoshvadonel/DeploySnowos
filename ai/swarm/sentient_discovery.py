import time
import socket
import logging
import json
import os
import hmac
import hashlib

_SECRETS_DIR = os.environ.get("SNOWOS_SECRETS_DIR", "/etc/snowos/secrets")
_SWARM_KEY_FILE = os.path.join(_SECRETS_DIR, "swarm.key")

def _load_swarm_key() -> bytes:
    try:
        if os.path.exists(_SWARM_KEY_FILE):
            with open(_SWARM_KEY_FILE, "rb") as f:
                k = f.read().strip()
                if len(k) >= 16:
                    return k
    except Exception:
        pass
    return b"snowos_default_swarm_secret_key_32"

_SWARM_SECRET = _load_swarm_key()

class SentientDiscovery:
    """Handles discovery and health tracking of SnowOS swarm peers with HMAC validation."""
    
    def __init__(self, port=49152):
        self.nodes = {} # {node_id: {health_data, last_seen}}
        self.logger = logging.getLogger("SnowOS.SwarmDiscovery")
        self.local_id = socket.gethostname()
        self.port = port
        
        # In multi-tenant environments, default to loopback unless network swarm is enabled
        enable_network = os.environ.get("SNOWOS_SWARM_NETWORK", "0") == "1"
        self.bind_ip = "0.0.0.0" if enable_network else "127.0.0.1"
        self.broadcast_ip = "255.255.255.255" if enable_network else "127.255.255.255"
        
        # Setup socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if enable_network:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(False)
        
        try:
            self.socket.bind((self.bind_ip, self.port))
            self.logger.info(f"Swarm: Discovery active on {self.bind_ip}:{self.port} (HMAC authenticated)")
        except Exception as e:
            self.logger.error(f"Swarm: Failed to bind discovery socket: {e}")

    def _sign(self, data_str: str) -> str:
        return hmac.new(_SWARM_SECRET, data_str.encode(), hashlib.sha256).hexdigest()

    def broadcast_presence(self, health_data):
        """Broadcast local node health to the swarm with HMAC authentication."""
        payload = {
            "node_id": self.local_id,
            "health": health_data,
            "timestamp": time.time()
        }
        raw_payload = json.dumps(payload, sort_keys=True)
        envelope = {
            "payload": payload,
            "signature": self._sign(raw_payload)
        }
        message = json.dumps(envelope).encode()
        
        try:
            self.socket.sendto(message, (self.broadcast_ip, self.port))
            self.logger.debug(f"Swarm: Broadcasted presence to {self.broadcast_ip}")
        except Exception as e:
            self.logger.error(f"Swarm: Broadcast failed: {e}")

    def listen_for_peers(self):
        """Receive presence updates from other nodes and verify HMAC signatures."""
        while True:
            try:
                data, addr = self.socket.recvfrom(4096)
                envelope = json.loads(data.decode())
                payload = envelope.get("payload")
                signature = envelope.get("signature")
                if not payload or not signature:
                    continue
                # Validate signature
                expected_sig = self._sign(json.dumps(payload, sort_keys=True))
                if not hmac.compare_digest(signature, expected_sig):
                    self.logger.warning(f"Swarm: Dropped unverified broadcast packet from {addr}")
                    continue
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

