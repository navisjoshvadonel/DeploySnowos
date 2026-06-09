"""
Stage 34 — Capability Token System

Tokens are cryptographically signed, immutable credential objects
bound to a specific task. They carry the exact set of permissions
that a task is allowed to exercise.

Design decisions:
  - Tokens use HMAC-SHA256 for integrity (not encryption — we're
    protecting against tampering, not secrecy).
  - Once created, all fields are read-only (enforced via __setattr__).
  - Expiration is checked on every validation call.
  - TokenStore is thread-safe for concurrent scheduler access.
"""

import hashlib
import hmac
import json
import time
import threading
import base64
from .capabilities import CapabilitySet
from distributed_identity.crypto import CryptoEngine


# Secret used for HMAC signing. In production this would come from
# a secure keystore; here we derive it from machine identity.
_TOKEN_SECRET = hashlib.sha256(b"snowos-cbsm-v1-secret").digest()


class CapabilityToken:
    """Immutable, signed capability credential for a single task."""

    __slots__ = (
        "_task_id", "_plan_id", "_user_id", "_role", "_capabilities", 
        "_issued_at", "_expires_at", "_node_origin", "_signature", "_frozen",
    )

    def __init__(self, task_id: str, plan_id: str, user_id: str, role: str,
                 capabilities: CapabilitySet, node_origin: str = "local",
                 ttl: int = 600, private_key: bytes = None):
        """
        Args:
            task_id: Unique task identifier.
            plan_id: Deterministic plan hash (Stage 32 link).
            capabilities: Immutable CapabilitySet.
            ttl: Time-to-live in seconds (default 10 min).
        """
        object.__setattr__(self, "_frozen", False)
        self._task_id = task_id
        self._plan_id = plan_id
        self._user_id = user_id
        self._role = role
        self._capabilities = capabilities
        self._issued_at = time.time()
        self._expires_at = self._issued_at + ttl
        self._node_origin = node_origin
        self._signature = self._sign(private_key)
        # Freeze the token — no further writes allowed
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AttributeError("CapabilityToken is immutable after creation")
        object.__setattr__(self, name, value)

    # ── Properties ──
    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def plan_id(self) -> str:
        return self._plan_id

    @property
    def capabilities(self) -> CapabilitySet:
        return self._capabilities

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def role(self) -> str:
        return self._role

    @property
    def issued_at(self) -> float:
        return self._issued_at

    @property
    def expires_at(self) -> float:
        return self._expires_at

    @property
    def signature(self) -> str:
        return self._signature

    # ── Signing & Validation ──
    def _sign(self, private_key: bytes = None) -> str:
        """Compute Ed25519 signature over the token's semantic content."""
        payload = json.dumps({
            "task_id": self._task_id,
            "plan_id": self._plan_id,
            "user_id": self._user_id,
            "role": self._role,
            "node_origin": self._node_origin,
            "caps": sorted(self._capabilities.to_list()),
            "issued": self._issued_at,
            "expires": self._expires_at,
        }, sort_keys=True)
        
        if not private_key:
            # Fallback to HMAC for purely local tokens if no node key provided
            # (Though in Stage 40, we prefer Ed25519 everywhere)
            return hmac.new(_TOKEN_SECRET, payload.encode(), hashlib.sha256).hexdigest()
        
        sig_bytes = CryptoEngine.sign(private_key, payload.encode())
        return base64.b64encode(sig_bytes).decode()

    def verify(self, public_key: str = None) -> bool:
        """Check signature integrity AND expiration."""
        if time.time() > self._expires_at:
            return False
            
        payload = json.dumps({
            "task_id": self._task_id,
            "plan_id": self._plan_id,
            "user_id": self._user_id,
            "role": self._role,
            "node_origin": self._node_origin,
            "caps": sorted(self._capabilities.to_list()),
            "issued": self._issued_at,
            "expires": self._expires_at,
        }, sort_keys=True).encode()

        if not public_key:
            # Fallback/Compat with HMAC
            expected = hmac.new(_TOKEN_SECRET, payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(self._signature, expected)
            
        sig_bytes = base64.b64decode(self._signature)
        return CryptoEngine.verify(public_key.encode(), sig_bytes, payload)

    def has_capability(self, required: str) -> bool:
        """Check whether this token grants a specific capability."""
        return self._capabilities.has(required)

    def to_dict(self) -> dict:
        return {
            "task_id": self._task_id,
            "plan_id": self._plan_id,
            "user_id": self._user_id,
            "role": self._role,
            "node_origin": self._node_origin,
            "capabilities": self._capabilities.to_list(),
            "issued_at": self._issued_at,
            "expires_at": self._expires_at,
            "signature": self._signature,
        }

def verify_distributed_token(token_data: dict, public_key: str) -> bool:
    """Helper to verify a token dict using a node's public key."""
    try:
        from .capabilities import CapabilitySet
        caps = CapabilitySet(token_data["capabilities"])
        # Reconstruct token object
        token = CapabilityToken(
            task_id=token_data["task_id"],
            plan_id=token_data["plan_id"],
            user_id=token_data["user_id"],
            role=token_data["role"],
            capabilities=caps,
            node_origin=token_data["node_origin"],
            ttl=int(token_data["expires_at"] - token_data["issued_at"])
        )
        # Override fields that are computed in init
        object.__setattr__(token, "_issued_at", token_data["issued_at"])
        object.__setattr__(token, "_expires_at", token_data["expires_at"])
        object.__setattr__(token, "_signature", token_data["signature"])
        
        return token.verify(public_key)
    except Exception:
        return False


class TokenStore:
    """Thread-safe in-memory store for active capability tokens.
    
    Tokens are keyed by task_id. Old tokens are purged periodically.
    """

    def __init__(self):
        self._tokens: dict[str, CapabilityToken] = {}
        self._lock = threading.Lock()

    def issue(self, token: CapabilityToken) -> None:
        with self._lock:
            self._tokens[token.task_id] = token

    def get(self, task_id: str) -> CapabilityToken | None:
        with self._lock:
            return self._tokens.get(task_id)

    def revoke(self, task_id: str) -> None:
        with self._lock:
            self._tokens.pop(task_id, None)

    def purge_expired(self) -> int:
        """Remove all expired tokens. Returns count removed."""
        now = time.time()
        removed = 0
        with self._lock:
            expired = [tid for tid, tok in self._tokens.items()
                       if now > tok.expires_at]
            for tid in expired:
                del self._tokens[tid]
                removed += 1
        return removed

    def active_count(self) -> int:
        with self._lock:
            return len(self._tokens)
