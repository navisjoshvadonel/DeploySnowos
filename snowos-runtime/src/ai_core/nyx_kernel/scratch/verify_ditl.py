import sys
import os
import json
import base64
from uuid import uuid4

# Add nyx to path
sys.path.append("/home/develop/snowos/nyx")

from distributed_identity.crypto import CryptoEngine
from distributed_identity.node_store import NodeStore
from distributed_identity.trust import TrustManager
from security.tokens import CapabilityToken, verify_distributed_token
from security.capabilities import CapabilitySet

def test_ditl_flow():
    print("--- Testing Stage 40: DITL Flow ---")
    
    # 1. Key Generation
    print("[1] Generating node keys...")
    priv, pub = CryptoEngine.generate_keypair()
    print(f"✔ Public Key: {pub[:30].decode()}...")
    
    # 2. Token Creation
    print("[2] Creating distributed token...")
    caps = CapabilitySet(["read", "execute"])
    token = CapabilityToken(
        task_id=str(uuid4()),
        plan_id="test-plan-123",
        user_id="user-456",
        role="admin",
        capabilities=caps,
        node_origin="node-alpha",
        private_key=priv
    )
    token_dict = token.to_dict()
    print(f"✔ Token created. Signature: {token_dict['signature'][:20]}...")
    
    # 3. Verification (Direct)
    print("[3] Verifying token directly...")
    is_valid = token.verify(public_key=pub.decode())
    if is_valid:
        print("✔ Token is VALID.")
    else:
        print("❌ Token is INVALID.")
        return False
        
    # 4. Verification (via Helper)
    print("[4] Verifying token via helper...")
    is_valid_helper = verify_distributed_token(token_dict, pub.decode())
    if is_valid_helper:
        print("✔ Helper verification SUCCESS.")
    else:
        print("❌ Helper verification FAILED.")
        return False
        
    # 5. Node Store & Trust
    print("[5] Testing NodeStore and TrustManager...")
    db_path = "/home/develop/snowos/nyx/scratch/test_network.db"
    if os.path.exists(db_path): os.remove(db_path)
    
    store = NodeStore(db_path)
    trust = TrustManager(store)
    
    node_id = "node-beta"
    trust.register_node(node_id, "http://localhost:8081", pub.decode())
    
    print(f"✔ Registered node {node_id}. Trusted: {trust.is_trusted(node_id)}")
    
    trust.trust_node(node_id)
    print(f"✔ Trusted node {node_id}. Trusted: {trust.is_trusted(node_id)}")
    
    # 6. Verify via TrustManager
    print("[6] Verifying token via TrustManager...")
    is_trusted_token = trust.verify_node_token(node_id, token_dict)
    if is_trusted_token:
        print("✔ TrustManager verification SUCCESS.")
    else:
        print("❌ TrustManager verification FAILED.")
        return False
        
    print("\n[✔] ALL DITL TESTS PASSED.")
    return True

if __name__ == "__main__":
    if test_ditl_flow():
        sys.exit(0)
    else:
        sys.exit(1)
