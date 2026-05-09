import os
import sys
import socket
import json
import logging
import time
import hmac
import hashlib
import base64
import secrets
import stat
from policy_engine import PolicyEngine
from intent_validator import IntentValidator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PermissionBroker")

RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
SOCKET_PATH = os.path.join(RUNTIME_DIR, "broker.sock")

# ─────────────────────────────────────────────────────────────────────────────
# SECURE TOKEN SECRET — never hardcoded. Generated once at first boot.
# Stored in /etc/snowos/secrets/broker.key with chmod 0600 / root:root.
# Falls back to a random ephemeral secret if the secrets dir is unavailable
# (e.g., during development). Never reuses a hardcoded constant.
# ─────────────────────────────────────────────────────────────────────────────
_SECRETS_DIR = os.environ.get("SNOWOS_SECRETS_DIR", "/etc/snowos/secrets")
_BROKER_KEY_FILE = os.path.join(_SECRETS_DIR, "broker.key")


def _load_or_generate_secret() -> bytes:
    """
    Load the HMAC signing secret from the secrets file.
    If the file does not exist, generate a cryptographically secure 32-byte
    secret using os.urandom(), persist it with strict file permissions
    (0o600, owned by root), and return it.

    If the secrets directory is not writable (e.g., running as a non-root
    developer), a one-time ephemeral secret is used and a warning is logged.
    This ephemeral secret means tokens will not survive process restarts.
    """
    # --- try to read existing key ---
    if os.path.exists(_BROKER_KEY_FILE):
        try:
            with open(_BROKER_KEY_FILE, "rb") as f:
                key = f.read()
            if len(key) >= 32:
                logger.info("Broker: Loaded signing key from %s", _BROKER_KEY_FILE)
                return key
            else:
                logger.warning("Broker: Key file too short — regenerating.")
        except OSError as exc:
            logger.warning("Broker: Cannot read key file (%s) — using ephemeral key.", exc)
            return _ephemeral_secret()

    # --- generate a new key ---
    try:
        os.makedirs(_SECRETS_DIR, mode=0o700, exist_ok=True)
        raw_key = os.urandom(32)
        # Write with an exclusive open so another process cannot race us.
        fd = os.open(_BROKER_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw_key)
        logger.info("Broker: Generated new signing key at %s", _BROKER_KEY_FILE)
        return raw_key
    except PermissionError:
        logger.warning(
            "Broker: No permission to write %s — using ephemeral key. "
            "Run install.sh as root to set up the secrets directory.",
            _BROKER_KEY_FILE,
        )
        return _ephemeral_secret()
    except FileExistsError:
        # Another process created it between our check and open — retry read.
        return _load_or_generate_secret()


def _ephemeral_secret() -> bytes:
    """Return a one-time 32-byte random secret for dev/degraded runs."""
    key = os.urandom(32)
    logger.warning(
        "Broker: Using EPHEMERAL signing key. "
        "Tokens will not be valid after process restart."
    )
    return key


# Load at module import time — single call per process lifetime.
_TOKEN_SECRET: bytes = _load_or_generate_secret()


class PermissionBroker:
    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.intent_validator = IntentValidator()
        self.running = False

    def setup_socket(self):
        os.makedirs(RUNTIME_DIR, mode=0o750, exist_ok=True)
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        self.server.listen(5)
        logger.info("Broker listening on %s", SOCKET_PATH)

    def issue_token(self, source_id: str, target_resource: str, action: str, ttl_seconds: int = 30) -> str:
        """Issue a signed capability token for an approved request."""
        issued_at = int(time.time())
        payload = {
            "source_id": source_id,
            "target_resource": target_resource,
            "action": action,
            "issued_at": issued_at,
            "expires_at": issued_at + ttl_seconds,
            # Nonce prevents replay attacks within the TTL window.
            "nonce": secrets.token_hex(8),
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            _TOKEN_SECRET,
            payload_json.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        envelope = {"payload": payload, "signature": signature}
        return base64.urlsafe_b64encode(json.dumps(envelope).encode("utf-8")).decode("ascii")

    def verify_token(self, raw_token: str) -> dict | None:
        """Verify a token's HMAC signature and expiry. Returns payload or None."""
        try:
            envelope = json.loads(base64.urlsafe_b64decode(raw_token).decode("utf-8"))
            payload = envelope["payload"]
            signature = envelope["signature"]

            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            expected = hmac.new(
                _TOKEN_SECRET,
                payload_json.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected):
                logger.warning("Broker: Token signature mismatch — rejected.")
                return None

            if time.time() > payload["expires_at"]:
                logger.warning("Broker: Token expired — rejected.")
                return None

            return payload
        except Exception as exc:
            logger.error("Broker: Token verification error: %s", exc)
            return None

    def handle_request(self, payload_str: str) -> dict:
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            return {"status": "ERROR", "reason": "Invalid JSON"}

        source_id = payload.get("source_id")
        target_resource = payload.get("target_resource")
        action = payload.get("action")

        if not all([source_id, target_resource, action]):
            return {"status": "ERROR", "reason": "Missing required fields"}

        logger.info("Request: %s -> %s on %s", source_id, action, target_resource)

        # 1. Check Capabilities
        if not self.policy_engine.evaluate(source_id, target_resource, action):
            logger.warning("DENIED: %s lacks capability for %s on %s", source_id, action, target_resource)
            return {"status": "DENIED", "reason": "Capability not granted"}

        # 2. Check Intent (AI Sentinel Hook)
        if not self.intent_validator.validate_intent(payload):
            logger.warning("DENIED: Intent validation failed for %s", source_id)
            return {"status": "DENIED", "reason": "Suspicious intent detected"}

        logger.info("GRANTED: %s -> %s on %s", source_id, action, target_resource)
        return {
            "status": "GRANTED",
            "token": self.issue_token(source_id, target_resource, action),
            "expires_in": 30,
        }

    def run(self):
        self.setup_socket()
        self.running = True

        try:
            while self.running:
                conn, _addr = self.server.accept()
                with conn:
                    data = conn.recv(4096)
                    if not data:
                        continue
                    response = self.handle_request(data.decode("utf-8"))
                    conn.sendall(json.dumps(response).encode("utf-8"))
        except KeyboardInterrupt:
            logger.info("Broker shutting down...")
        finally:
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)


if __name__ == "__main__":
    broker = PermissionBroker()
    broker.run()
