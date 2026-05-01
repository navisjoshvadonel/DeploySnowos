"""
Stage 34 — Capability Schema

Defines granular, scoped permissions for all system actions.
Capabilities follow a category.action[:scope] format.

Design decisions:
  - Capabilities are simple strings for fast comparison and serialization.
  - Scopes use glob-style matching for path-based permissions.
  - CapabilitySet is immutable after creation (frozenset internally).
  - Default-deny: a missing capability means denial.
"""

import fnmatch


class Capability:
    """Static registry of all recognized capability strings."""

    # ── File Operations ──
    FILE_READ      = "file.read"
    FILE_WRITE     = "file.write"
    FILE_DELETE    = "file.delete"
    FILE_EXECUTE   = "file.execute"

    # ── Process Operations ──
    PROCESS_SPAWN  = "process.spawn"
    PROCESS_KILL   = "process.kill"

    # ── System Operations ──
    SYSTEM_MODIFY  = "system.modify"
    SYSTEM_CONFIG  = "system.config"

    # ── Network Operations ──
    NETWORK_REQUEST = "network.request"
    NETWORK_LISTEN  = "network.listen"

    # ── Sandbox Operations ──
    SANDBOX_ESCAPE  = "sandbox.escape"   # Extremely restricted

    ALL = frozenset([
        FILE_READ, FILE_WRITE, FILE_DELETE, FILE_EXECUTE,
        PROCESS_SPAWN, PROCESS_KILL,
        SYSTEM_MODIFY, SYSTEM_CONFIG,
        NETWORK_REQUEST, NETWORK_LISTEN,
        SANDBOX_ESCAPE,
    ])


class CapabilitySet:
    """An immutable set of capabilities, optionally scoped.

    Internally stores entries like:
        "file.write"                   → unscoped (matches everything)
        "file.write:/workspace/*"      → scoped (glob match)
        "network.request:api.github.com" → scoped (exact/glob)

    Once created, the set CANNOT be mutated — this is critical
    to prevent runtime privilege escalation.
    """

    def __init__(self, entries: list[str]):
        # Freeze immediately — no mutation after construction
        self._entries = frozenset(entries)

    def has(self, required: str) -> bool:
        """Check if this set grants the required capability.

        Supports scoped matching:
            required = "file.write:/workspace/test.py"
            granted  = "file.write:/workspace/*"  → match
            granted  = "file.write"                → match (unscoped = all)
        """
        # Split required into base and scope
        if ":" in required:
            req_base, req_scope = required.split(":", 1)
        else:
            req_base, req_scope = required, None

        for entry in self._entries:
            if ":" in entry:
                ent_base, ent_scope = entry.split(":", 1)
            else:
                ent_base, ent_scope = entry, None

            if ent_base != req_base:
                continue

            # Unscoped grant matches everything in that category
            if ent_scope is None:
                return True

            # If required has no scope but grant is scoped, still allow
            # (the grant is more specific, but covers generic requests)
            if req_scope is None:
                return True

            # Glob match for scoped entries
            if fnmatch.fnmatch(req_scope, ent_scope):
                return True

        return False

    def to_list(self) -> list[str]:
        return sorted(self._entries)

    def __repr__(self):
        return f"CapabilitySet({self.to_list()})"

    def __contains__(self, item):
        return self.has(item)
