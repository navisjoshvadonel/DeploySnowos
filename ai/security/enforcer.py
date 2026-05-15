"""
Stage 34 — Enforcement Engine

The runtime gate that sits between command analysis and execution.
Every command must pass through enforce() before it reaches the sandbox.

Design decisions:
  - Strict default-deny: if a token is missing, expired, or lacks
    the required capability, execution is BLOCKED.
  - Every check (pass or fail) is logged to the observability DB
    for audit purposes.
  - The enforcer does NOT execute commands — it only returns a
    verdict. The caller (run_plan) decides what to do.
  - Thread-safe: uses the TokenStore which is already locked.
"""

import time
from .tokens import TokenStore
from .analyzer import CommandAnalyzer


class EnforcementResult:
    """Outcome of a capability enforcement check."""

    __slots__ = ("allowed", "command", "required", "missing", "reason")

    def __init__(self, allowed: bool, command: str,
                 required: list[str], missing: list[str],
                 reason: str = ""):
        self.allowed = allowed
        self.command = command
        self.required = required
        self.missing = missing
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "command": self.command,
            "required": self.required,
            "missing": self.missing,
            "reason": self.reason,
        }


class EnforcementEngine:
    """Pre-execution capability gate.

    Usage:
        result = enforcer.enforce(task_id, command)
        if not result.allowed:
            # block execution, log violation
    """

    def __init__(self, token_store: TokenStore, storage=None):
        self.token_store = token_store
        self.storage = storage  # Observability DB for audit logging

    def enforce(self, task_id: str, command: str) -> EnforcementResult:
        """Validate that a task has permission to run a command.

        Steps:
            1. Look up the task's token.
            2. Verify token integrity and expiration.
            3. Analyze the command to extract required capabilities.
            4. Check each required capability against the token.
            5. Log the result and return verdict.
        """
        # 1. Token lookup
        token = self.token_store.get(task_id)
        if token is None:
            result = EnforcementResult(
                allowed=False, command=command,
                required=[], missing=[],
                reason="No capability token found for task"
            )
            self._audit(task_id, result)
            return result

        # 2. Integrity & expiration check
        if not token.verify():
            result = EnforcementResult(
                allowed=False, command=command,
                required=[], missing=[],
                reason="Token failed verification (expired or tampered)"
            )
            self._audit(task_id, result)
            return result

        # 3. Analyze command
        required = CommandAnalyzer.analyze(command)

        # 4. Check each required capability
        missing = [cap for cap in required if not token.has_capability(cap)]

        if missing:
            result = EnforcementResult(
                allowed=False, command=command,
                required=required, missing=missing,
                reason=f"Missing capabilities: {', '.join(missing)}"
            )
        else:
            result = EnforcementResult(
                allowed=True, command=command,
                required=required, missing=[],
                reason="All capabilities granted"
            )

        # 5. Audit log
        self._audit(task_id, result)
        return result

    def _audit(self, task_id: str, result: EnforcementResult):
        """Log the enforcement decision to the observability DB."""
        if self.storage:
            token = self.token_store.get(task_id)
            self.storage.save_capability_event(
                task_id=task_id,
                plan_id=token.plan_id if token else None,
                command=result.command,
                required_capability=", ".join(result.required),
                granted=result.allowed,
                reason=result.reason,
            )
