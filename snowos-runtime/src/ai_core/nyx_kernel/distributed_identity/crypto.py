import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

class CryptoEngine:
    """Handles asymmetric Ed25519 signing and verification for distributed identity."""
    
    @staticmethod
    def generate_keypair():
        """Generate a new Ed25519 key pair."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        return priv_bytes, pub_bytes

    @staticmethod
    def sign(private_key_pem: bytes, data: bytes) -> bytes:
        """Sign data using the private key."""
        private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        return private_key.sign(data)

    @staticmethod
    def verify(public_key_bytes: bytes, signature: bytes, data: bytes) -> bool:
        """Verify signature using the public key."""
        try:
            # Load public key (might be OpenSSH or PEM)
            try:
                public_key = serialization.load_ssh_public_key(public_key_bytes)
            except ValueError:
                public_key = serialization.load_pem_public_key(public_key_bytes)
                
            public_key.verify(signature, data)
            return True
        except Exception:
            return False

    @staticmethod
    def get_node_keys(key_dir: str = "~/.snowos/"):
        """Load or generate node-specific keys."""
        key_path = os.path.expanduser(os.path.join(key_dir, "node_key"))
        pub_path = key_path + ".pub"
        
        if os.path.exists(key_path) and os.path.exists(pub_path):
            with open(key_path, "rb") as f:
                priv = f.read()
            with open(pub_path, "rb") as f:
                pub = f.read()
            return priv, pub
        
        # Generate new keys
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        priv, pub = CryptoEngine.generate_keypair()
        
        with open(key_path, "wb") as f:
            f.write(priv)
            os.chmod(key_path, 0o600)
        with open(pub_path, "wb") as f:
            f.write(pub)
            
        return priv, pub
