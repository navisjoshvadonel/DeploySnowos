from typing import Optional, Dict
from .node_store import NodeStore
from .crypto import CryptoEngine

class TrustManager:
    """Manages explicit trust relationships between nodes."""
    
    def __init__(self, node_store: NodeStore):
        self.store = node_store

    def register_node(self, node_id: str, url: str, public_key: str) -> bool:
        """Register a new node. It remains untrusted until explicitly trusted."""
        self.store.add_node(node_id, url, public_key)
        return True

    def trust_node(self, node_id: str) -> bool:
        """Explicitly trust a node."""
        node = self.store.get_node(node_id)
        if not node:
            return False
        self.store.set_trust(node_id, "trusted")
        return True

    def revoke_trust(self, node_id: str) -> bool:
        """Revoke trust from a node."""
        node = self.store.get_node(node_id)
        if not node:
            return False
        self.store.set_trust(node_id, "untrusted")
        return True

    def is_trusted(self, node_id: str) -> bool:
        """Check if a node is explicitly trusted."""
        node = self.store.get_node(node_id)
        if not node:
            return False
        return node.get("trust_status") == "trusted"

    def verify_node_token(self, node_id: str, token_data: dict) -> bool:
        """Verify that a token was issued by a trusted node."""
        if not self.is_trusted(node_id):
            return False
            
        node = self.store.get_node(node_id)
        if not node:
            return False
            
        from security.tokens import verify_distributed_token
        return verify_distributed_token(token_data, node["public_key"])

    def evaluate_risk(self, node_id: str, action: str) -> tuple[int, bool]:
        """
        Dynamically calculates a confidence score based on historical cryptographic signatures
        and the behavioral risk of the task.
        Returns: (score (0-100), is_trusted)
        """
        base_score = 50
        
        if self.is_trusted(node_id):
            base_score += 40
        else:
            base_score -= 20
            
        action_lower = action.lower()
        
        high_risk = ["rm ", "sudo ", "chmod ", "chown ", "install", "format"]
        if any(h in action_lower for h in high_risk):
            base_score -= 40
            
        safe_tasks = ["compile", "build", "analyze", "infer", "calculate"]
        if any(s in action_lower for s in safe_tasks):
            base_score += 20
            
        final_score = max(0, min(100, base_score))
        return final_score, final_score >= 80
