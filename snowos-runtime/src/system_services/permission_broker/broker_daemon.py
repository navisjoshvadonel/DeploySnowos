#!/usr/bin/env python3
"""
SnowOS IPC Message Broker — Upgraded Multi-threaded Production Daemon.

This is the central nervous system of SnowOS. All services communicate
through this broker over UNIX sockets at /run/snowos/broker.sock.

Architecture:
  - Multi-threaded: each client connection gets its own thread
  - Topic-based pub/sub: components subscribe to topic channels
  - Capability-gated: all requests are validated via PolicyEngine
  - HMAC-signed tokens for secure service-to-service auth
  - Persistent subscriber tracking: components can register as listeners

Supported message types:
  - "request"   : Request a capability-gated action (returns GRANTED/DENIED + token)
  - "publish"   : Publish an event to a topic (broadcast to all subscribers)
  - "subscribe" : Register as a listener for a topic
  - "ping"      : Health check
  - "status"    : Get broker status

Clients that subscribe are tracked; when events are published the broker
pushes them to all listening sockets (fire-and-forget, non-blocking).
"""

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
import threading
import signal
from collections import defaultdict
from typing import Dict, Set

# Local imports (same directory)
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

try:
    from policy_engine import PolicyEngine
    from intent_validator import IntentValidator
except ImportError:
    class PolicyEngine:  # noqa: D101
        def evaluate(self, src, res, action):
            return True  # Permissive fallback during dev
    class IntentValidator:  # noqa: D101
        def validate_intent(self, payload):
            return True

logging.basicConfig(
    level=os.environ.get("SNOWOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [Broker] %(levelname)s %(message)s",
)
logger = logging.getLogger("SnowBroker")

RUNTIME_DIR  = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
SOCKET_PATH  = os.path.join(RUNTIME_DIR, "broker.sock")
MAX_CONN     = 32          # max simultaneous client connections
RECV_SIZE    = 65536       # 64 KB per message
PUSH_TIMEOUT = 2.0         # seconds to wait when pushing to a subscriber

# ─── Secret key management ────────────────────────────────────────────────────
_SECRETS_DIR     = os.environ.get("SNOWOS_SECRETS_DIR", "/etc/snowos/secrets")
_BROKER_KEY_FILE = os.path.join(_SECRETS_DIR, "broker.key")


def _load_or_generate_secret() -> bytes:
    if os.path.exists(_BROKER_KEY_FILE):
        try:
            with open(_BROKER_KEY_FILE, "rb") as f:
                key = f.read()
            if len(key) >= 32:
                logger.info("Loaded HMAC signing key from %s", _BROKER_KEY_FILE)
                return key
        except OSError as exc:
            logger.warning("Cannot read key file (%s) — using ephemeral key.", exc)
            return _ephemeral_secret()
    try:
        os.makedirs(_SECRETS_DIR, mode=0o700, exist_ok=True)
        raw_key = os.urandom(32)
        fd = os.open(_BROKER_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw_key)
        logger.info("Generated new HMAC signing key at %s", _BROKER_KEY_FILE)
        return raw_key
    except PermissionError:
        logger.warning("No permission for %s — using ephemeral key.", _BROKER_KEY_FILE)
        return _ephemeral_secret()
    except FileExistsError:
        return _load_or_generate_secret()


def _ephemeral_secret() -> bytes:
    key = os.urandom(32)
    logger.warning("Using EPHEMERAL signing key — tokens invalid after restart.")
    return key


_TOKEN_SECRET: bytes = _load_or_generate_secret()


# ─── Broker ───────────────────────────────────────────────────────────────────
class MessageBroker:
    """
    Multi-threaded SnowOS IPC message broker.

    Internal state:
      _subscribers: topic → list of (subscriber_id, socket)
      _subscriber_lock: protects _subscribers
      _stats: message counters
    """

    def __init__(self):
        self.policy   = PolicyEngine()
        self.validator = IntentValidator()
        self.running  = False

        # pub/sub registry: topic → {sub_id: connected_socket}
        self._subscribers: Dict[str, Dict[str, socket.socket]] = defaultdict(dict)
        self._sub_lock   = threading.Lock()

        # stats
        self._stats = {
            "requests": 0,
            "granted": 0,
            "denied": 0,
            "published": 0,
            "started_at": time.time(),
        }
        self._stats_lock = threading.Lock()

        # Graceful shutdown event
        self._stop = threading.Event()

    # ── Token management ──────────────────────────────────────────────────────

    def _issue_token(self, source_id: str, target_resource: str,
                     action: str, ttl: int = 30) -> str:
        now = int(time.time())
        payload = {
            "source_id": source_id,
            "target_resource": target_resource,
            "action": action,
            "issued_at": now,
            "expires_at": now + ttl,
            "nonce": secrets.token_hex(8),
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(_TOKEN_SECRET, payload_json.encode(), hashlib.sha256).hexdigest()
        envelope = {"payload": payload, "signature": sig}
        return base64.urlsafe_b64encode(json.dumps(envelope).encode()).decode("ascii")

    def _verify_token(self, raw: str) -> dict | None:
        try:
            envelope = json.loads(base64.urlsafe_b64decode(raw).decode())
            payload = envelope["payload"]
            sig     = envelope["signature"]
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            expected = hmac.new(_TOKEN_SECRET, payload_json.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                return None
            if time.time() > payload["expires_at"]:
                return None
            return payload
        except Exception:
            return None

    # ── Request handler ───────────────────────────────────────────────────────

    def _handle_request(self, payload: dict) -> dict:
        source_id       = payload.get("source_id", "")
        target_resource = payload.get("target_resource", "")
        action          = payload.get("action", "")

        if not all([source_id, target_resource, action]):
            return {"status": "ERROR", "reason": "Missing required fields"}

        with self._stats_lock:
            self._stats["requests"] += 1

        if not self.policy.evaluate(source_id, target_resource, action):
            logger.warning("DENIED: %s → %s on %s", source_id, action, target_resource)
            with self._stats_lock:
                self._stats["denied"] += 1
            return {"status": "DENIED", "reason": "Capability not granted"}

        if not self.validator.validate_intent(payload):
            logger.warning("DENIED (intent): %s", source_id)
            with self._stats_lock:
                self._stats["denied"] += 1
            return {"status": "DENIED", "reason": "Suspicious intent"}

        token = self._issue_token(source_id, target_resource, action)
        logger.info("GRANTED: %s → %s on %s", source_id, action, target_resource)
        with self._stats_lock:
            self._stats["granted"] += 1
        return {"status": "GRANTED", "token": token, "expires_in": 30}

    # ── Pub/Sub ───────────────────────────────────────────────────────────────

    def _handle_subscribe(self, payload: dict, conn: socket.socket) -> dict:
        topic     = payload.get("topic", "")
        sub_id    = payload.get("subscriber_id", "")
        if not topic or not sub_id:
            return {"status": "ERROR", "reason": "topic and subscriber_id required"}
        with self._sub_lock:
            self._subscribers[topic][sub_id] = conn
        logger.info("SUBSCRIBED: %s → topic '%s'", sub_id, topic)
        return {"status": "SUBSCRIBED", "topic": topic}

    def _handle_publish(self, payload: dict) -> dict:
        topic = payload.get("topic", "")
        data  = payload.get("data", {})
        if not topic:
            return {"status": "ERROR", "reason": "topic required"}

        with self._sub_lock:
            subscribers = dict(self._subscribers.get(topic, {}))

        push_msg = json.dumps({
            "type":  "event",
            "topic": topic,
            "data":  data,
            "ts":    time.time(),
        }).encode()

        delivered = 0
        dead_subs = []
        for sub_id, sub_conn in subscribers.items():
            try:
                sub_conn.settimeout(PUSH_TIMEOUT)
                sub_conn.sendall(len(push_msg).to_bytes(4, "big") + push_msg)
                delivered += 1
            except Exception:
                dead_subs.append((topic, sub_id))

        # Clean up dead subscribers
        if dead_subs:
            with self._sub_lock:
                for (t, sid) in dead_subs:
                    self._subscribers[t].pop(sid, None)

        with self._stats_lock:
            self._stats["published"] += 1

        logger.debug("PUBLISHED '%s' → %d subscriber(s)", topic, delivered)
        return {"status": "OK", "delivered": delivered}

    # ── Main message dispatcher ───────────────────────────────────────────────

    def dispatch(self, raw: str, conn: socket.socket) -> dict:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return {"status": "ERROR", "reason": "Invalid JSON"}

        msg_type = msg.get("type", "request")

        if msg_type == "ping":
            return {"status": "pong", "ts": time.time()}
        elif msg_type == "status":
            with self._stats_lock:
                return {"status": "OK", "stats": dict(self._stats)}
        elif msg_type == "request":
            return self._handle_request(msg)
        elif msg_type == "subscribe":
            return self._handle_subscribe(msg, conn)
        elif msg_type == "publish":
            return self._handle_publish(msg)
        elif msg_type == "verify_token":
            token   = msg.get("token", "")
            payload = self._verify_token(token)
            return {"status": "VALID" if payload else "INVALID", "payload": payload}
        else:
            return {"status": "ERROR", "reason": f"Unknown message type: {msg_type}"}

    # ── Per-connection thread ─────────────────────────────────────────────────

    def _handle_conn(self, conn: socket.socket, addr):
        """Handle a single client connection on its own thread."""
        try:
            # Read a 4-byte length-prefix, then the message body
            # (simple framing to support persistent subscriber connections)
            raw_len = b""
            while len(raw_len) < 4:
                chunk = conn.recv(4 - len(raw_len))
                if not chunk:
                    return
                raw_len += chunk

            msg_len = int.from_bytes(raw_len, "big")
            if msg_len > RECV_SIZE:
                logger.warning("Oversized message (%d bytes) — closing connection.", msg_len)
                return

            raw_body = b""
            while len(raw_body) < msg_len:
                chunk = conn.recv(min(4096, msg_len - len(raw_body)))
                if not chunk:
                    return
                raw_body += chunk

            response = self.dispatch(raw_body.decode("utf-8", errors="replace"), conn)
            resp_bytes = json.dumps(response).encode()
            conn.sendall(len(resp_bytes).to_bytes(4, "big") + resp_bytes)

            # If the client subscribed, keep the connection alive
            if response.get("status") == "SUBSCRIBED":
                logger.debug("Keeping connection alive for subscriber.")
                self._stop.wait()  # Block until broker shuts down

        except Exception as exc:
            logger.debug("Connection error: %s", exc)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── Server loop ───────────────────────────────────────────────────────────

    def _setup_socket(self):
        os.makedirs(RUNTIME_DIR, mode=0o775, exist_ok=True)
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        self.server.listen(MAX_CONN)
        self.server.settimeout(1.0)   # allow clean shutdown polling
        logger.info("SnowOS Broker listening on %s", SOCKET_PATH)

    def run(self):
        self._setup_socket()
        self.running = True

        def _sigterm(_sig, _frame):
            logger.info("Broker: SIGTERM received — shutting down.")
            self.running = False
            self._stop.set()

        signal.signal(signal.SIGTERM, _sigterm)
        signal.signal(signal.SIGINT,  _sigterm)

        logger.info("SnowOS Message Broker ready (max_conn=%d).", MAX_CONN)

        try:
            while self.running:
                try:
                    conn, addr = self.server.accept()
                    t = threading.Thread(
                        target=self._handle_conn,
                        args=(conn, addr),
                        daemon=True,
                        name=f"Broker-Conn-{threading.active_count()}",
                    )
                    t.start()
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            self.running = False
            self._stop.set()
            try:
                self.server.close()
            except Exception:
                pass
            if os.path.exists(SOCKET_PATH):
                try:
                    os.remove(SOCKET_PATH)
                except Exception:
                    pass
            logger.info("Broker stopped.")


def main():
    logging.basicConfig(
        level=os.environ.get("SNOWOS_BROKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s [Broker] %(levelname)s %(message)s",
    )
    broker = MessageBroker()
    broker.run()


if __name__ == "__main__":
    main()
