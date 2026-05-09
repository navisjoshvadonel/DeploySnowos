"""
Stage 34 — Command Analyzer

Parses shell commands and extracts the set of capabilities required
to execute them. This is the bridge between human-readable commands
and the machine-enforced capability model.

Design decisions:
  - Pattern-based detection for reliability and speed.
  - Each pattern maps a command regex → required capabilities.
  - Scoped capabilities are generated when path/host info is available.
  - Returns a list of required capability strings for the enforcer.
  - Extensible: new patterns can be added without modifying core logic.
"""

import re
from .capabilities import Capability
from .behavioral import BehavioralSecurity

behavioral_engine = BehavioralSecurity()


# ── Pattern Registry ──
# Each entry: (compiled_regex, handler_function)
# Handler receives the match object and returns list[str] of capabilities.

def _file_read_handler(m):
    target = m.group("path") or ""
    base = Capability.FILE_READ
    return [f"{base}:{target}"] if target else [base]

def _file_write_handler(m):
    target = m.group("path") or ""
    base = Capability.FILE_WRITE
    return [f"{base}:{target}"] if target else [base]

def _file_delete_handler(m):
    target = m.group("path") or ""
    base = Capability.FILE_DELETE
    return [f"{base}:{target}"] if target else [base]

def _network_handler(m):
    url = m.group("url") or ""
    # Extract hostname from URL
    host_match = re.match(r'https?://([^/:]+)', url)
    host = host_match.group(1) if host_match else ""
    base = Capability.NETWORK_REQUEST
    return [f"{base}:{host}"] if host else [base]

def _process_spawn_handler(m):
    return [Capability.PROCESS_SPAWN]

def _process_kill_handler(m):
    return [Capability.PROCESS_KILL]

def _system_modify_handler(m):
    return [Capability.SYSTEM_MODIFY]


_PATTERNS = [
    # ── File reads ──
    (re.compile(r"^cat\s+(?P<path>\S+)"), _file_read_handler),
    (re.compile(r"^less\s+(?P<path>\S+)"), _file_read_handler),
    (re.compile(r"^head\s+.*?(?P<path>\S+)$"), _file_read_handler),
    (re.compile(r"^tail\s+.*?(?P<path>\S+)$"), _file_read_handler),
    (re.compile(r"^grep\s+.*?(?P<path>\S+)$"), _file_read_handler),
    (re.compile(r"^ls\b"), lambda m: [Capability.FILE_READ]),

    # ── File writes ──
    (re.compile(r"^(?:tee|nano|vim?|emacs)\s+(?P<path>\S+)"), _file_write_handler),
    (re.compile(r"^cp\s+\S+\s+(?P<path>\S+)"), _file_write_handler),
    (re.compile(r"^mv\s+\S+\s+(?P<path>\S+)"), _file_write_handler),
    (re.compile(r"^mkdir\s+(?:-p\s+)?(?P<path>\S+)"), _file_write_handler),
    (re.compile(r"^touch\s+(?P<path>\S+)"), _file_write_handler),
    (re.compile(r".*?>+\s*(?P<path>\S+)"), _file_write_handler),  # redirects

    # ── File deletes ──
    (re.compile(r"^rm\s+(?:-[rRf]+\s+)?(?P<path>\S+)"), _file_delete_handler),
    (re.compile(r"^rmdir\s+(?P<path>\S+)"), _file_delete_handler),

    # ── File execution ──
    (re.compile(r"^(?:bash|sh|python3?|node|ruby)\s+(?P<path>\S+)"),
     lambda m: [Capability.FILE_EXECUTE, f"{Capability.FILE_READ}:{m.group('path')}"]),
    (re.compile(r"^chmod\s+\+x\s+(?P<path>\S+)"),
     lambda m: [Capability.FILE_EXECUTE, f"{Capability.FILE_WRITE}:{m.group('path')}"]),

    # ── Network ──
    (re.compile(r"^curl\s+.*?(?P<url>https?://\S+)"), _network_handler),
    (re.compile(r"^wget\s+.*?(?P<url>https?://\S+)"), _network_handler),
    (re.compile(r"^pip\s+install\b"), lambda m: [Capability.NETWORK_REQUEST, Capability.FILE_WRITE]),
    (re.compile(r"^npm\s+install\b"), lambda m: [Capability.NETWORK_REQUEST, Capability.FILE_WRITE]),
    (re.compile(r"^apt(?:-get)?\s+install\b"),
     lambda m: [Capability.NETWORK_REQUEST, Capability.SYSTEM_MODIFY]),
    (re.compile(r"^git\s+(?:clone|pull|push|fetch)\b"),
     lambda m: [Capability.NETWORK_REQUEST, Capability.FILE_WRITE]),

    # ── Process ──
    (re.compile(r"^kill\s"), _process_kill_handler),
    (re.compile(r"^pkill\s"), _process_kill_handler),
    (re.compile(r"^nohup\s"), _process_spawn_handler),

    # ── System modifications ──
    (re.compile(r"^sudo\s"), _system_modify_handler),
    (re.compile(r"^systemctl\s"), _system_modify_handler),
    (re.compile(r"^service\s"), _system_modify_handler),
    (re.compile(r"^useradd\b"), _system_modify_handler),
    (re.compile(r"^usermod\b"), _system_modify_handler),
    (re.compile(r"^chown\b"),
     lambda m: [Capability.SYSTEM_MODIFY, Capability.FILE_WRITE]),
]

# Paths that require system.modify regardless of operation
_PROTECTED_PATHS = frozenset([
    "/etc", "/usr", "/boot", "/sbin", "/var/log",
    "/proc", "/sys", "/dev",
])


class CommandAnalyzer:
    """Extracts required capabilities from a shell command string."""

    @staticmethod
    def analyze(command: str) -> list[str]:
        """Return a list of capability strings required by `command`."""
        cmd = command.strip()
        if not cmd:
            return []

        required = []

        # Run through pattern registry
        for pattern, handler in _PATTERNS:
            m = pattern.match(cmd)
            if m:
                required.extend(handler(m))

        # Check for protected path access
        for path in _PROTECTED_PATHS:
            # Use word boundaries to avoid matching /home/develop as /dev
            if re.search(rf"\b{re.escape(path)}\b", cmd):
                if Capability.SYSTEM_MODIFY not in required:
                    required.append(Capability.SYSTEM_MODIFY)
                break

        # Pipe chains: each segment may need its own capabilities
        if "|" in cmd:
            segments = cmd.split("|")
            for seg in segments[1:]:
                sub = CommandAnalyzer.analyze(seg.strip())
                required.extend(sub)

        # Default: if nothing matched, require process.spawn
        # because the user is running *something*
        if not required:
            required.append(Capability.PROCESS_SPAWN)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for r in required:
            if r not in seen:
                seen.add(r)
                deduped.append(r)

        # MODERN OS FEATURE: Behavioral Anomaly Detection
        is_risky, score = behavioral_engine.is_anomalous(cmd)
        if is_risky:
            # If the command is anomalous, we escalate the required capabilities
            # to include SYSTEM_MODIFY even if it's just a 'cat' or 'ls'.
            if Capability.SYSTEM_MODIFY not in deduped:
                deduped.append(Capability.SYSTEM_MODIFY)
                # We could also add a 'REASON' metadata but for now just escalate
                
        return deduped
