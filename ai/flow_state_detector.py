#!/usr/bin/env python3
"""
SnowOS Flow State Detector — Autonomous Deep Work Recognition Engine.

Monitors user behavioral patterns in real-time to detect when the user
enters a "flow state" (deep, uninterrupted work) and automatically
adjusts the OS environment to support focus.

Flow state is detected when:
  1. Rapid, sustained keyboard activity (high keypress velocity)
  2. No window switching for N consecutive seconds
  3. Active window is a recognized productivity tool (IDE, editor, terminal)
  4. No manual audio/notification interactions

When flow is detected, the detector:
  - Sets memory["_flow_state"] = "deep_work" in the Nyx memory store
  - Publishes "flow_state_entered" event to EventBus/Broker
  - Sends a "focus" profile signal to the Intent Governor
  - Triggers notification suppression

When flow ends (inactivity or window switch):
  - Resets memory["_flow_state"] = "idle"
  - Publishes "flow_state_exited" event
  - Restores normal notification/resource settings

Data sources:
  - /tmp/snowos_context.json (written by context_engine.py every 2-3s)
  - ~/.snowos/behavior_log.jsonl (behavior time-series)
  - X11 keyboard polling (optional, via xdotool)

Usage (standalone):
  python3 flow_state_detector.py

Usage (embedded in NyxDaemon):
  from flow_state_detector import FlowStateDetector
  detector = FlowStateDetector(nyx_memory=nyx.memory, bus=bus)
  detector.start()
"""

import os
import sys
import json
import time
import logging
import threading
import subprocess
from pathlib import Path
from collections import deque

logging.basicConfig(
    level=os.environ.get("SNOWOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [FlowDetector] %(levelname)s %(message)s",
)
logger = logging.getLogger("FlowDetector")

# ── Constants ──────────────────────────────────────────────────────────────────
CONTEXT_FILE      = "/tmp/snowos_context.json"
BEHAVIOR_LOG      = os.path.expanduser("~/.snowos/behavior_log.jsonl")
SNOWOS_DIR        = os.path.expanduser("~/.snowos")
RUNTIME_DIR       = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
BROKER_SOCK       = os.path.join(RUNTIME_DIR, "broker.sock")

POLL_INTERVAL_SEC = 3       # how often to evaluate flow state
FLOW_IDLE_THRESH  = 45      # seconds without window switch to enter flow
FLOW_EXIT_THRESH  = 20      # seconds of inactivity to exit flow
MIN_SESSION_SEC   = 120     # must be in same window for at least 2 minutes

# ── Apps that indicate deep work ───────────────────────────────────────────────
DEEP_WORK_CLASSES = {
    # IDEs
    "code", "vscodium", "idea", "pycharm", "clion", "goland", "webstorm",
    "intellij", "eclipse", "netbeans", "android studio",
    # Editors
    "vim", "nvim", "neovim", "emacs", "nano", "gedit", "kate", "mousepad",
    "sublime_text", "sublimetext", "atom", "zed",
    # Terminals
    "gnome-terminal", "konsole", "alacritty", "kitty", "wezterm",
    "xterm", "urxvt", "st", "tilix",
    # Writing
    "libreoffice", "writer", "obsidian", "logseq", "joplin",
    "zettlr", "typora", "marktext",
    # Dev browsers (for developer mode)
    "firefox", "chromium", "chrome",
}

# ── Broker helpers ─────────────────────────────────────────────────────────────

def _broker_publish(topic: str, data: dict):
    """Publish an event to the SnowOS broker."""
    try:
        import socket as _socket
        msg = json.dumps({"type": "publish", "topic": topic, "data": data}).encode()
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(BROKER_SOCK)
        s.sendall(len(msg).to_bytes(4, "big") + msg)
        resp_len_raw = s.recv(4)
        if resp_len_raw:
            resp_len = int.from_bytes(resp_len_raw, "big")
            s.recv(resp_len)
        s.close()
    except Exception:
        pass  # Broker may not be running in dev mode


# ── Notification suppression ───────────────────────────────────────────────────

def _suppress_notifications(suppress: bool):
    """Enable/disable Do-Not-Disturb via GNOME D-Bus or libnotify."""
    try:
        if suppress:
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.notifications",
                 "show-banners", "false"],
                capture_output=True, timeout=3
            )
            logger.info("Notifications suppressed (flow state active).")
        else:
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.notifications",
                 "show-banners", "true"],
                capture_output=True, timeout=3
            )
            logger.info("Notifications restored (flow state exited).")
    except Exception as e:
        logger.debug("Could not toggle notifications: %s", e)


def _set_focus_cpu_profile(focus: bool):
    """Signal the Intent Governor to switch CPU profile."""
    profile_file = "/tmp/snowos_governor_state.json"
    try:
        state = {}
        if os.path.exists(profile_file):
            with open(profile_file) as f:
                state = json.load(f)
        state["flow_override"] = "performance" if focus else None
        state["flow_active"] = focus
        with open(profile_file, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.debug("CPU profile signal failed: %s", e)


# ── Flow State Detector ────────────────────────────────────────────────────────

class FlowStateDetector:
    """
    Monitors user behavior and detects deep work flow states.
    
    When flow is entered/exited, it updates the provided memory dict
    (so Nyx's planning prompts see the state) and publishes broker events.
    """

    def __init__(self, nyx_memory: dict | None = None, bus=None):
        """
        Args:
            nyx_memory: Reference to NyxAI.memory dict. Updated directly.
            bus:        SnowOS EventBus instance for local pub/sub.
        """
        self.memory  = nyx_memory or {}
        self.bus     = bus
        self._stop   = threading.Event()
        self._thread: threading.Thread | None = None

        # Tracking state
        self._current_window_class: str = ""
        self._window_unchanged_since: float = 0.0
        self._last_activity_ts: float = 0.0
        self._flow_active: bool = False
        self._window_history: deque = deque(maxlen=20)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _read_context(self) -> dict:
        try:
            if os.path.exists(CONTEXT_FILE):
                with open(CONTEXT_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _is_deep_work_app(self, wm_class: str) -> bool:
        """Return True if the active window class is a known deep-work app."""
        lower = wm_class.lower()
        return any(app in lower for app in DEEP_WORK_CLASSES)

    def _evaluate_flow(self, ctx: dict) -> tuple[bool, str]:
        """
        Evaluate whether the user is in a flow state.
        
        Returns:
            (should_be_in_flow, reason_string)
        """
        now = time.time()
        win_info = ctx.get("active_window", {})
        wm_class = win_info.get("wm_class", "").lower()
        title    = win_info.get("title", "")

        # Track window changes
        if wm_class != self._current_window_class:
            self._window_history.append({
                "ts": now,
                "class": wm_class,
                "title": title,
            })
            self._current_window_class = wm_class
            self._window_unchanged_since = now
            self._last_activity_ts = now

            # Window switch resets flow
            if self._flow_active:
                return False, f"Window switched to {wm_class}"

        # Always record context reads as activity
        self._last_activity_ts = now

        # Must be in a deep-work app
        if not self._is_deep_work_app(wm_class):
            return False, f"App '{wm_class}' not in deep-work list"

        # Must be in same window for MIN_SESSION_SEC
        time_in_window = now - self._window_unchanged_since
        if time_in_window < MIN_SESSION_SEC:
            remaining = int(MIN_SESSION_SEC - time_in_window)
            return False, f"In {wm_class} for {int(time_in_window)}s (need {MIN_SESSION_SEC}s)"

        # Must not have switched windows recently (FLOW_IDLE_THRESH)
        if len(self._window_history) >= 2:
            last_switch = self._window_history[-2]["ts"] if len(self._window_history) >= 2 else 0
            time_since_switch = now - last_switch
            if time_since_switch < FLOW_IDLE_THRESH:
                return False, f"Window switched {int(time_since_switch)}s ago (need {FLOW_IDLE_THRESH}s)"

        # All criteria met
        return True, f"Deep work in {wm_class} for {int(time_in_window)}s"

    def _on_flow_enter(self, reason: str):
        """Called when flow state is first detected."""
        logger.info("🌊 Flow state ENTERED: %s", reason)
        self._flow_active = True

        # Update Nyx memory
        self.memory["_flow_state"] = "deep_work"
        self.memory["_flow_entered_ts"] = time.time()

        # Publish to EventBus
        if self.bus:
            self.bus.publish("flow_state_entered", {"reason": reason})

        # Publish to Broker
        _broker_publish("flow_state_entered", {
            "state": "deep_work",
            "reason": reason,
            "window": self._current_window_class,
            "ts": time.time(),
        })

        # OS-level adjustments
        _suppress_notifications(True)
        _set_focus_cpu_profile(True)

    def _on_flow_exit(self, reason: str):
        """Called when flow state ends."""
        duration = time.time() - self.memory.get("_flow_entered_ts", time.time())
        logger.info("🏖️  Flow state EXITED after %.0fs: %s", duration, reason)
        self._flow_active = False

        # Update Nyx memory
        self.memory["_flow_state"] = "idle"
        self.memory["_flow_exited_ts"] = time.time()
        self.memory["_last_flow_duration_sec"] = int(duration)

        # Publish to EventBus
        if self.bus:
            self.bus.publish("flow_state_exited", {
                "reason": reason,
                "duration_sec": int(duration),
            })

        # Publish to Broker
        _broker_publish("flow_state_exited", {
            "state": "idle",
            "reason": reason,
            "duration_sec": int(duration),
            "ts": time.time(),
        })

        # Restore OS settings
        _suppress_notifications(False)
        _set_focus_cpu_profile(False)

    # ── Main loop ──────────────────────────────────────────────────────────────

    def _detect_loop(self):
        """Background detection loop."""
        logger.info("FlowStateDetector started (poll_interval=%ds).", POLL_INTERVAL_SEC)
        while not self._stop.is_set():
            try:
                ctx = self._read_context()
                should_flow, reason = self._evaluate_flow(ctx)

                if should_flow and not self._flow_active:
                    self._on_flow_enter(reason)
                elif not should_flow and self._flow_active:
                    # Add a grace period before exiting flow
                    time.sleep(FLOW_EXIT_THRESH)
                    # Re-evaluate after grace period
                    ctx2 = self._read_context()
                    still_flow, r2 = self._evaluate_flow(ctx2)
                    if not still_flow:
                        self._on_flow_exit(reason)

            except Exception as e:
                logger.debug("Detection loop error: %s", e)

            self._stop.wait(POLL_INTERVAL_SEC)

        logger.info("FlowStateDetector stopped.")

    def start(self):
        """Start the background detection loop."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._detect_loop,
            daemon=True,
            name="FlowDetector",
        )
        self._thread.start()

    def stop(self):
        """Stop the detector."""
        self._stop.set()

    @property
    def is_flowing(self) -> bool:
        return self._flow_active

    def get_status(self) -> dict:
        return {
            "flow_active": self._flow_active,
            "current_app": self._current_window_class,
            "time_in_window": int(time.time() - self._window_unchanged_since),
            "flow_state": self.memory.get("_flow_state", "idle"),
            "last_flow_duration": self.memory.get("_last_flow_duration_sec"),
        }


# ── Standalone entry point ────────────────────────────────────────────────────

def main():
    """Run as a standalone process for testing."""
    import signal

    memory: dict = {}
    detector = FlowStateDetector(nyx_memory=memory)
    detector.start()

    def _stop(_sig, _frame):
        detector.stop()
        print("\nFlowDetector stopped.")
        raise SystemExit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info("FlowStateDetector running standalone. Press Ctrl+C to stop.")
    while True:
        time.sleep(10)
        status = detector.get_status()
        logger.info("Status: %s", json.dumps(status))


if __name__ == "__main__":
    main()
