#!/usr/bin/env python3
"""
SnowOS Cognitive Intent Pre-fetching & Resource Governor.

Analyzes behavioral time-series data to:
  1. Predict upcoming app usage patterns
  2. Pre-cache binaries into RAM via vmtouch
  3. Set CPU governor based on inferred user focus level
  4. Emit power state recommendations

Design: polling-based with 60-second evaluation cycle.
No tight loop — sleeps between evaluations, stops cleanly on SIGTERM.
"""
import os
import sys
import json
import time
import signal
import logging
import subprocess
import threading
from pathlib import Path
from collections import defaultdict, Counter
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [IntentGovernor] %(levelname)s %(message)s",
)
logger = logging.getLogger("IntentGovernor")

SNOWOS_DIR    = os.path.expanduser("~/.snowos")
BEHAVIOR_LOG  = os.path.join(SNOWOS_DIR, "behavior_log.jsonl")
STATE_FILE    = "/tmp/snowos_governor_state.json"
EVAL_INTERVAL = 60   # seconds between evaluations
LOOKAHEAD_MIN = 10   # predict 10 minutes ahead

# ─── CPU Governor ─────────────────────────────────────────────────────────────
_CPU_GOV_PATH = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"

_GOV_MAP = {
    "performance": "performance",
    "balanced":    "schedutil",
    "efficiency":  "powersave",
}

def _set_cpu_governor(profile: str):
    """Write CPU frequency governor. Requires write access or polkit."""
    gov = _GOV_MAP.get(profile, "schedutil")
    cpu_base = Path("/sys/devices/system/cpu")
    if not cpu_base.exists():
        logger.debug("CPU governor path not available.")
        return
    success = 0
    for cpu_dir in cpu_base.glob("cpu[0-9]*"):
        gov_file = cpu_dir / "cpufreq" / "scaling_governor"
        if gov_file.exists():
            try:
                gov_file.write_text(gov)
                success += 1
            except PermissionError:
                # Try via tee with sudo (polkit)
                try:
                    subprocess.run(
                        f"echo {gov} | sudo tee {gov_file} > /dev/null",
                        shell=True, timeout=3, capture_output=True,
                    )
                    success += 1
                except Exception:
                    pass
            except Exception:
                pass
    if success:
        logger.info(f"CPU governor set to '{gov}' ({profile}) on {success} cores.")

# ─── vmtouch Pre-caching ──────────────────────────────────────────────────────
_VMTOUCH_AVAIL: bool | None = None

def _has_vmtouch() -> bool:
    global _VMTOUCH_AVAIL
    if _VMTOUCH_AVAIL is None:
        _VMTOUCH_AVAIL = subprocess.run(
            ["which", "vmtouch"], capture_output=True
        ).returncode == 0
    return _VMTOUCH_AVAIL

def _precache_binary(binary_name: str):
    """Pre-load a binary and its libraries into the page cache."""
    if not _has_vmtouch():
        logger.debug("vmtouch not available — skipping pre-cache.")
        return
    try:
        path_result = subprocess.run(
            ["which", binary_name], capture_output=True, text=True, timeout=2
        )
        binary_path = path_result.stdout.strip()
        if not binary_path:
            return
        subprocess.Popen(
            ["vmtouch", "-t", binary_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        logger.info(f"Pre-caching '{binary_name}' ({binary_path})")
    except Exception as e:
        logger.debug(f"Pre-cache failed for {binary_name}: {e}")

# ─── Behavior Analysis ────────────────────────────────────────────────────────
_APP_BINARY_MAP = {
    "code":        "code",
    "vscode":      "code",
    "firefox":     "firefox",
    "chromium":    "chromium-browser",
    "terminal":    "bash",
    "docker":      "docker",
    "vim":         "vim",
    "nvim":        "nvim",
    "gimp":        "gimp",
    "blender":     "blender",
    "python":      "python3",
    "node":        "node",
    "htop":        "htop",
    "slack":       "slack",
}

def _normalize_app(title: str) -> str:
    """Extract a canonical app name from a window title."""
    title_lower = title.lower()
    for keyword, app in _APP_BINARY_MAP.items():
        if keyword in title_lower:
            return app
    # Fallback: use first word
    return title.split()[0].lower() if title.split() else "unknown"


def _load_behavior_log(max_entries: int = 2000) -> list:
    """Load recent behavioral log entries."""
    if not os.path.exists(BEHAVIOR_LOG):
        return []
    entries = []
    try:
        with open(BEHAVIOR_LOG) as f:
            lines = f.readlines()[-max_entries:]
        for line in lines:
            try:
                entries.append(json.loads(line.strip()))
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Behavior log read error: {e}")
    return entries


def _predict_next_apps(lookahead_minutes: int = LOOKAHEAD_MIN) -> list:
    """
    Predict which apps will likely be needed in the next N minutes
    based on historical patterns by hour-of-day and day-of-week.
    Returns list of binary names to pre-cache (de-duplicated, top-5).
    """
    entries = _load_behavior_log()
    if not entries:
        return []

    now = time.localtime()
    target_hour = (now.tm_hour + (now.tm_min + lookahead_minutes) // 60) % 24
    target_dow  = now.tm_wday

    # Count app frequency for matching time slots
    freq: Counter = Counter()
    for entry in entries:
        if abs(entry.get("hour", -99) - target_hour) <= 1 and \
           entry.get("day_of_week", -1) == target_dow:
            app = _normalize_app(entry.get("active_app", ""))
            if app and app != "unknown":
                freq[app] += 1

    # Return top-5 most frequent
    return [app for app, _ in freq.most_common(5)]


def _infer_power_profile(entries: list) -> str:
    """
    Infer power profile from recent entries.
    Returns 'performance' | 'balanced' | 'efficiency'.
    """
    if not entries:
        return "balanced"

    recent = entries[-20:]  # last 20 entries
    loads  = [e.get("load", 0) for e in recent]
    avg_load = sum(loads) / len(loads) if loads else 0

    # Count mode distribution
    modes = [e.get("mode", "active") for e in recent]
    mode_counts = Counter(modes)
    dominant = mode_counts.most_common(1)[0][0]

    if avg_load > 2.0 or dominant == "high_stress":
        return "performance"
    if avg_load < 0.3 and dominant == "idle":
        return "efficiency"
    return "balanced"


# ─── Governor Engine ──────────────────────────────────────────────────────────
class IntentGovernor:
    DESTRUCTIVE_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+\*",
        r"chmod\s+-R\s+777\s+/",
        r"chown\s+-R\s+.*:/",
        r">\s*/etc/",
        r">\s*/boot/",
        r"mkfs\.",
        r"dd\s+if=.*of=/dev/",
        r"apt-get\s+(remove|purge|autoremove)\s+-y",
        r"dpkg\s+--remove\s+--force",
        r"killall\s+-9\s+systemd",
    ]

    def __init__(self):
        self._stop = threading.Event()
        self._last_profile: str = "balanced"
        self._precached: set = set()
        self.compiled_patterns = [re.compile(p) for p in self.DESTRUCTIVE_PATTERNS]

    def check_intent(self, command: str) -> dict:
        """Returns a dict containing intent risk level and reason."""
        cmd_lower = command.lower()
        
        for p in self.compiled_patterns:
            if p.search(cmd_lower):
                return {
                    "safe": False,
                    "risk": "HIGH",
                    "reason": f"Matches destructive pattern: {p.pattern}"
                }
                
        if "sudo " in cmd_lower and "rm " in cmd_lower:
            return {
                "safe": False,
                "risk": "HIGH",
                "reason": "Privileged removal detected."
            }

        return {
            "safe": True,
            "risk": "LOW",
            "reason": "No destructive patterns detected."
        }

    def evaluate(self):
        """Run one governor evaluation cycle."""
        entries = _load_behavior_log()

        # 1. Power profile
        profile = _infer_power_profile(entries)
        if profile != self._last_profile:
            logger.info(f"Power profile changed: {self._last_profile} → {profile}")
            _set_cpu_governor(profile)
            self._last_profile = profile

        # 2. Predictive pre-caching
        predicted_apps = _predict_next_apps()
        for app in predicted_apps:
            if app not in self._precached:
                _precache_binary(app)
                self._precached.add(app)

        # Expire cache after 2 hours
        if len(self._precached) > 50:
            self._precached.clear()

        # 3. Write state
        state = {
            "timestamp":      time.time(),
            "power_profile":  profile,
            "predicted_apps": predicted_apps,
            "precached":      list(self._precached)[:20],
        }
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

        return state

    def run(self):
        logger.info("IntentGovernor started.")

        def _stop(sig, frame):
            logger.info("IntentGovernor shutting down...")
            self._stop.set()
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        # First evaluation immediately
        try:
            self.evaluate()
        except Exception as e:
            logger.error(f"Initial evaluation failed: {e}")

        while not self._stop.is_set():
            self._stop.wait(EVAL_INTERVAL)
            if self._stop.is_set():
                break
            try:
                self.evaluate()
            except Exception as e:
                logger.error(f"Evaluation error: {e}")

        logger.info("IntentGovernor stopped.")


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--once" in sys.argv:
        gov = IntentGovernor()
        state = gov.evaluate()
        print(json.dumps(state, indent=2))
    else:
        IntentGovernor().run()
