"""
SnowOS Runtime — NodeManager & SwarmClient
==========================================
Extracted from nyx.py (Stage 28/40 — DITL Distributed Identity Layer).

NodeManager — maintains the registry of peer Nyx nodes, including trust status
              and public keys.

SwarmClient — makes authenticated HTTP calls to peer nodes, propagating the
              caller's capability token and distributed tracing headers.
"""

import json
import time
import uuid
import logging

import requests

logger = logging.getLogger("SnowOS.NodeClient")


class NodeManager:
    """
    Maintains the local registry of known peer Nyx nodes.

    Trust lifecycle:
        add_node → (untrusted) → trust_node → (trusted) → calls allowed
    """

    def __init__(self, db_path: str):
        from distributed_identity.node_store import NodeStore
        from distributed_identity.trust import TrustManager
        self.store = NodeStore(db_path)
        self.trust = TrustManager(self.store)

    def add_node(self, node_id: str, url: str, public_key: str):
        self.store.add_node(node_id, url, public_key)

    def get_nodes(self) -> list:
        return self.store.list_nodes()


class SwarmClient:
    """
    Makes authenticated cross-node HTTP calls in the Nyx swarm.

    Each outgoing request carries:
        - A short-lived CapabilityToken in the Authorization header
        - Distributed tracing headers (X-Nyx-Trace-ID, X-Nyx-Parent-Span-ID)
        - The calling node's identity (X-Nyx-Node-ID)
    """

    def __init__(self, nyx_agent):
        self.nyx = nyx_agent

    def call_node(self, node_id: str, endpoint: str, data: dict | None = None) -> dict:
        """
        Make an authenticated call to a peer node's API endpoint.

        Args:
            node_id:  The target node's registered ID.
            endpoint: Path on the peer (e.g. "/api/execute").
            data:     Optional JSON body (triggers POST; GET if None).

        Returns:
            Parsed JSON response dict, or {"error": "..."} on failure.
        """
        node = self.nyx.node_manager.store.get_node(node_id)
        if not node:
            return {"error": f"Node {node_id} not found"}

        if node["trust_status"] != "trusted":
            return {"error": f"Node {node_id} is not trusted. Trust it first via 'nyx node trust'."}

        url = node["url"].rstrip("/") + endpoint

        # Build a cross-node capability token
        try:
            from security.tokens import CapabilityToken
            from security.capabilities import CapabilitySet

            token = CapabilityToken(
                task_id=str(uuid.uuid4()),
                plan_id="cross-node-execution",
                user_id=self.nyx.current_user["user_id"],
                role=self.nyx.current_user["role"],
                capabilities=CapabilitySet(["read", "execute"]),
                node_origin=self.nyx.node_id,
                private_key=self.nyx.node_priv_key,
            )
            auth_header = f"Bearer {json.dumps(token.to_dict())}"
        except Exception as exc:
            logger.warning("SwarmClient: Token generation failed (%s) — call aborted.", exc)
            return {"error": "Token generation failed"}

        headers = {
            "Authorization": auth_header,
            "X-Nyx-Node-ID": self.nyx.node_id,
            "Content-Type": "application/json",
        }

        # Propagate distributed tracing context
        current_span = self.nyx.telemetry.tracer.get_current_span()
        if current_span:
            headers["X-Nyx-Trace-ID"] = current_span["trace_id"]
            headers["X-Nyx-Parent-Span-ID"] = current_span["span_id"]

        trace_id = current_span["trace_id"] if current_span else uuid.uuid4().hex
        parent_id = current_span["span_id"] if current_span else None
        span_id = self.nyx.telemetry.start_span(
            name=f"remote_call:{endpoint}",
            type="network",
            trace_id=trace_id,
            parent_id=parent_id,
            exec_node_id=node_id,
        )
        start_time = time.time()

        try:
            if data:
                res = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                res = requests.get(url, headers=headers, timeout=10)

            latency = time.time() - start_time
            status = "SUCCESS" if res.status_code == 200 else "ERROR"
            self.nyx.telemetry.end_span(
                span_id, status,
                metadata={"latency": latency, "endpoint": endpoint, "status_code": res.status_code},
            )

            if res.status_code == 200:
                return res.json()
            return {"error": f"Node returned {res.status_code}: {res.text}"}

        except Exception as exc:
            self.nyx.telemetry.end_span(span_id, "ERROR", metadata={"error": str(exc)})
            return {"error": f"Connection failed: {exc}"}
