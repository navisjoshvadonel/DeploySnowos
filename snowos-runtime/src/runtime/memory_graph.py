"""
SnowOS Runtime — MemoryGraph (Execution Memory Graph / EMG)
============================================================
Extracted from nyx.py (Stage 16).

The EMG is a persistent, append-only graph of every execution Nyx performs.
Nodes represent plans, commands, files, and failures. Edges encode causal
relationships (CAUSED_BY, CREATED, MODIFIED, FAILED_DUE_TO, PART_OF).

The graph can be queried in natural language by passing an LLM function,
which reasons over the 40 most-recent nodes.
"""

import os
import json
import uuid
import datetime
import logging

logger = logging.getLogger("SnowOS.MemoryGraph")


class MemoryGraph:
    """
    Persistent Execution Memory Graph (EMG).

    Node types:
        execution_plan | command | file_created | file_modified |
        process_started | failure_event

    Edge relations (stored on source node):
        CREATED | MODIFIED | EXECUTED_BY | CAUSED_BY | PART_OF | FAILED_DUE_TO
    """

    def __init__(self, emg_file: str):
        self.emg_file = emg_file
        os.makedirs(os.path.dirname(emg_file), exist_ok=True)
        self.graph = self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if os.path.exists(self.emg_file):
            try:
                with open(self.emg_file) as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("MemoryGraph: Could not load EMG (%s) — starting fresh.", exc)
        return {"nodes": {}, "edges": []}

    def _save(self):
        with open(self.emg_file, "w") as f:
            json.dump(self.graph, f, indent=2)

    # ── Node builders ─────────────────────────────────────────────────────────

    def _make_node(self, node_type: str, metadata: dict) -> str:
        node_id = str(uuid.uuid4())[:12]
        self.graph["nodes"][node_id] = {
            "id": node_id,
            "type": node_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "metadata": metadata,
        }
        return node_id

    def _add_edge(self, src: str, rel: str, dst: str):
        self.graph["edges"].append({"src": src, "rel": rel, "dst": dst})

    # ── Public API ────────────────────────────────────────────────────────────

    def update(
        self,
        plan: list[str],
        diff: dict,
        execution_id: str,
        is_valid: bool,
        cwd: str,
        user_input: str = "",
    ) -> str:
        """Convert an execution run into EMG nodes + edges and persist."""

        # 1. Plan node
        plan_id = self._make_node("execution_plan", {
            "execution_id": execution_id,
            "user_input": user_input,
            "cwd": cwd,
            "steps": len(plan),
            "verified": is_valid,
        })

        # 2. Command nodes
        for cmd in plan:
            cmd_id = self._make_node("command", {"cmd": cmd, "cwd": cwd})
            self._add_edge(plan_id, "CAUSED_BY", cmd_id)
            self._add_edge(cmd_id, "PART_OF", plan_id)

        # 3. File nodes from diff
        for path in diff.get("created", []):
            fid = self._make_node("file_created", {"path": path})
            self._add_edge(plan_id, "CREATED", fid)

        for path in diff.get("modified", []):
            fid = self._make_node("file_modified", {"path": path})
            self._add_edge(plan_id, "MODIFIED", fid)

        # 4. Failure node
        if not is_valid:
            fail_id = self._make_node("failure_event", {
                "execution_id": execution_id,
                "plan": plan,
            })
            self._add_edge(plan_id, "FAILED_DUE_TO", fail_id)

        self._save()
        return plan_id

    def query(self, question: str, llm_fn) -> str:
        """Use an LLM function to reason over the graph and answer a question."""
        node_count = len(self.graph["nodes"])
        edge_count = len(self.graph["edges"])

        # Most recent 40 nodes to avoid token bloat
        recent_nodes = list(self.graph["nodes"].values())[-40:]
        summary = json.dumps({
            "total_nodes": node_count,
            "total_edges": edge_count,
            "recent_nodes": recent_nodes,
        })

        prompt = (
            "You are a graph-based memory retrieval engine for an AI operating system.\n"
            "Answer the user's question using the Execution Memory Graph below.\n"
            "Be specific: mention file paths, commands, timestamps, and execution IDs where relevant.\n"
            "If nothing relevant is found, say so clearly.\n\n"
            f"User Question: {question}\n\n"
            f"Memory Graph (recent):\n{summary}"
        )
        return llm_fn(prompt) or "Memory query failed."
