"""
Stage 34 — Policy Engine

Determines which capabilities a task receives based on its type,
plan metadata, and historical behaviour from the observability layer.

Design decisions:
  - Three task classes: USER, REPLAY, AUTONOMOUS — each with a
    progressively more restrictive default grant.
  - Replay tasks are special: they receive ONLY the capabilities
    that were used in the original execution (from DEL records).
  - Autonomous tasks get read-only by default. Any write/network
    action requires explicit user approval or policy override.
  - The engine is stateless — it computes tokens on demand from
    inputs, making it safe for concurrent use.
"""

from .capabilities import Capability, CapabilitySet
from .tokens import CapabilityToken, TokenStore


class TaskType:
    USER       = "user"
    REPLAY     = "replay"
    AUTONOMOUS = "autonomous"


# ── Default capability grants per task type ──
_DEFAULT_POLICIES = {
    TaskType.USER: [
        Capability.FILE_READ,
        Capability.FILE_WRITE,
        Capability.FILE_DELETE,
        Capability.FILE_EXECUTE,
        Capability.PROCESS_SPAWN,
        Capability.NETWORK_REQUEST,
    ],
    TaskType.REPLAY: [
        # Replay gets nothing by default — capabilities are
        # reconstructed from the original execution record.
    ],
    TaskType.AUTONOMOUS: [
        Capability.FILE_READ,
        Capability.PROCESS_SPAWN,
        # Read-only + spawn. No writes, no network, no system mods.
    ],
}

_ROLE_POLICIES = {
    "admin": [
        Capability.FILE_READ, Capability.FILE_WRITE, Capability.FILE_DELETE,
        Capability.FILE_EXECUTE, Capability.PROCESS_SPAWN, Capability.PROCESS_KILL,
        Capability.NETWORK_REQUEST, Capability.SYSTEM_MODIFY, Capability.SYSTEM_CONFIG,
    ],
    "developer": [
        Capability.FILE_READ, Capability.FILE_WRITE, Capability.FILE_DELETE,
        Capability.FILE_EXECUTE, Capability.PROCESS_SPAWN, Capability.NETWORK_REQUEST,
    ],
    "viewer": [
        Capability.FILE_READ,
    ],
    "system": [
        Capability.FILE_READ, Capability.FILE_WRITE, Capability.FILE_DELETE,
        Capability.FILE_EXECUTE, Capability.PROCESS_SPAWN, Capability.PROCESS_KILL,
        Capability.NETWORK_REQUEST, Capability.SYSTEM_MODIFY, Capability.SYSTEM_CONFIG,
    ],
}

# Capabilities that ALWAYS require explicit approval regardless of type
_APPROVAL_REQUIRED = frozenset([
    Capability.SYSTEM_MODIFY,
    Capability.SYSTEM_CONFIG,
    Capability.SANDBOX_ESCAPE,
    Capability.PROCESS_KILL,
])


class PolicyEngine:
    """Computes capability tokens for tasks based on policy rules."""

    def __init__(self, token_store: TokenStore):
        self.token_store = token_store

    def create_token(self, task_id: str, plan_id: str,
                     user_id: str, role: str,
                     task_type: str = TaskType.USER,
                     replay_caps: list[str] | None = None,
                     extra_caps: list[str] | None = None,
                     ttl: int = 600) -> CapabilityToken:
        """Create and store a capability token for a task.

        Args:
            task_id: Unique task identifier.
            plan_id: Deterministic plan ID (Stage 32).
            task_type: One of TaskType.USER / REPLAY / AUTONOMOUS.
            replay_caps: If task_type is REPLAY, the exact caps from
                         the original execution.
            extra_caps: Additional capabilities (e.g. user-approved).
            ttl: Token lifetime in seconds.

        Returns:
            A signed, immutable CapabilityToken.
        """
        # Start with base role policy
        role_caps = set(_ROLE_POLICIES.get(role, _ROLE_POLICIES["viewer"]))
        
        # Intersection with task type policy for restrictions
        task_policy = set(_DEFAULT_POLICIES.get(task_type, []))
        
        if task_type == TaskType.REPLAY:
            caps = set() # Replay reconstruction handled below
        else:
            # Grant capabilities that are in BOTH role policy AND task type policy
            # (unless it's a USER task, then we grant full role policy)
            if task_type == TaskType.USER:
                caps = role_caps
            else:
                caps = role_caps.intersection(task_policy)

        caps = list(caps)

        if task_type == TaskType.REPLAY and replay_caps:
            # Replay gets EXACTLY what was used originally — no more
            caps = list(replay_caps)
        
        if extra_caps:
            for cap in extra_caps:
                if cap not in caps:
                    caps.append(cap)

        # Never grant approval-required caps without explicit inclusion
        # in extra_caps (which comes from user confirmation)
        for cap in list(caps):
            base = cap.split(":")[0] if ":" in cap else cap
            if base in _APPROVAL_REQUIRED and cap not in (extra_caps or []):
                caps.remove(cap)

        cap_set = CapabilitySet(caps)
        token = CapabilityToken(task_id, plan_id, user_id, role, cap_set, ttl=ttl)
        self.token_store.issue(token)
        return token

    @staticmethod
    def requires_approval(capability: str) -> bool:
        """Check if a capability requires explicit user approval."""
        base = capability.split(":")[0] if ":" in capability else capability
        return base in _APPROVAL_REQUIRED

    @staticmethod
    def get_policy_summary() -> dict:
        """Return a human-readable summary of all policies."""
        return {
            task_type: sorted(caps)
            for task_type, caps in _DEFAULT_POLICIES.items()
        }
