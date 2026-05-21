#!/usr/bin/env python3
"""
SnowOS AI Context Engine — upgraded for SnowOS next-gen cognitive OS.

Features:
  1. Real active-window detection via xdotool / wmctrl
  2. System telemetry (CPU, memory, battery)
  3. Behavioral time-series logging to ~/.snowos/behavior_log.jsonl
  4. VLM screenshot capture (1fps, focused window crop)
  5. Writes enriched state to /tmp/snowos_context.json

Design: event-driven with timed polling. No tight infinite loops —
every poll sleeps 2-3 seconds and can be stopped via SIGTERM/SIGINT.
"""
import os
import sys
import json
import time
import signal
import logging
import subprocess
import threading
import hashlib
import base64
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ContextEngine] %(levelname)s %(message)s",
)
logger = logging.getLogger("ContextEngine")

# ── Paths ─────────────────────────────────────────────────────────────────────
CONTEXT_FILE   = "/tmp/snowos_context.json"
VISUAL_FILE    = "/tmp/snowos_visual_context.b64"
INSIGHT_FILE   = "/tmp/snowos_vlm_insight.json"
SNOWOS_DIR     = os.path.expanduser("~/.snowos")
BEHAVIOR_LOG   = os.path.join(SNOWOS_DIR, "behavior_log.jsonl")
POLL_INTERVAL  = 2       # seconds between context polls
BEHAVIOR_EVERY = 60      # seconds between behavior log entries
VISUAL_EVERY   = 5       # seconds between screenshot captures


# ── Window Detection ──────────────────────────────────────────────────────────
def _run(cmd: list, timeout: int = 3) -> str:
    """Run a subprocess and return stdout, empty string on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def get_active_window_info() -> dict:
    """
    Detect the currently active window using xdotool or wmctrl.
    Returns {title, pid, wm_class, desktop}.
    Falls back gracefully when no display is available.
    """
    # Try xdotool
    win_id = _run(["xdotool", "getactivewindow"])
    if win_id:
        title    = _run(["xdotool", "getwindowname",    win_id])
        pid_str  = _run(["xdotool", "getwindowpid",     win_id])
        wm_class = _run(["xprop", "-id", win_id, "WM_CLASS"])
        return {
            "title":    title or "Unknown",
            "pid":      int(pid_str) if pid_str.isdigit() else 0,
            "wm_class": wm_class.split('"')[1] if '"' in wm_class else "",
            "win_id":   win_id,
            "method":   "xdotool",
        }

    # Fallback: wmctrl -a doesn't work well; parse `wmctrl -l`
    wmctrl_out = _run(["wmctrl", "-l"])
    if wmctrl_out:
        lines = wmctrl_out.splitlines()
        if lines:
            parts = lines[0].split(None, 3)
            return {
                "title":    parts[3] if len(parts) > 3 else "Unknown",
                "pid":      0,
                "wm_class": "",
                "win_id":   parts[0] if parts else "",
                "method":   "wmctrl",
            }

    # Last resort: /proc-based guess
    return {
        "title":    "Unknown",
        "pid":      0,
        "wm_class": "",
        "win_id":   "",
        "method":   "fallback",
    }


# ── System Telemetry ──────────────────────────────────────────────────────────
def get_system_telemetry() -> dict:
    load1, load5, load15 = os.getloadavg()

    # Memory
    mem_info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                mem_info[k.strip()] = v.strip().split()[0]
        mem_total = int(mem_info.get("MemTotal", 0))
        mem_avail = int(mem_info.get("MemAvailable", 0))
        mem_used_pct = round((1 - mem_avail / mem_total) * 100, 1) if mem_total else 0
    except Exception:
        mem_used_pct = 0

    # Battery
    battery = {}
    bat_path = Path("/sys/class/power_supply")
    if bat_path.exists():
        for bat in bat_path.iterdir():
            cap_file = bat / "capacity"
            status_file = bat / "status"
            if cap_file.exists():
                try:
                    battery = {
                        "capacity":  int(cap_file.read_text().strip()),
                        "status":    status_file.read_text().strip() if status_file.exists() else "Unknown",
                    }
                    break
                except Exception:
                    pass

    return {
        "load_1min":      round(load1, 2),
        "load_5min":      round(load5, 2),
        "load_15min":     round(load15, 2),
        "mem_used_pct":   mem_used_pct,
        "battery":        battery,
    }


# ── Behavioral Logging ────────────────────────────────────────────────────────
def append_behavior_log(entry: dict):
    """Append one timestamped entry to the JSONL behavioral log."""
    os.makedirs(SNOWOS_DIR, exist_ok=True)
    try:
        with open(BEHAVIOR_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Behavior log write failed: {e}")


# ── Screenshot / Visual Context ───────────────────────────────────────────────
def capture_visual_context() -> bool:
    """
    Capture a compressed, low-res screenshot of the focused window.
    Writes base64-encoded JPEG to VISUAL_FILE.
    Returns True on success.
    """
    # Try scrot (lightweight X11 screenshot tool)
    tmp_img = "/tmp/snowos_snap.jpg"
    try:
        # -u: focused window, -q: quality 40 (small)
        result = subprocess.run(
            ["scrot", "-u", "-q", "40", tmp_img],
            capture_output=True, timeout=3,
        )
        if result.returncode == 0 and os.path.exists(tmp_img):
            with open(tmp_img, "rb") as f:
                data = f.read()
            encoded = base64.b64encode(data).decode()
            with open(VISUAL_FILE, "w") as f:
                f.write(encoded)
            os.remove(tmp_img)
            return True
    except Exception:
        pass

    # Try import (ImageMagick)
    try:
        result = subprocess.run(
            ["import", "-window", "root", "-resize", "320x180", "-quality", "40", tmp_img],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0 and os.path.exists(tmp_img):
            with open(tmp_img, "rb") as f:
                data = f.read()
            encoded = base64.b64encode(data).decode()
            with open(VISUAL_FILE, "w") as f:
                f.write(encoded)
            os.remove(tmp_img)
            return True
    except Exception:
        pass

    return False


# ── Main Engine ───────────────────────────────────────────────────────────────
class ContextEngine:
    def __init__(self):
        self._stop = threading.Event()
        self._last_behavior_ts = 0.0
        self._last_visual_ts   = 0.0
        self._iteration        = 0

    def _build_context(self) -> dict:
        win    = get_active_window_info()
        telem  = get_system_telemetry()
        ts     = time.time()

        # Derive a simple focus mode from load
        if telem["load_1min"] > 2.5:
            mode = "high_stress"
        elif telem["load_1min"] < 0.5:
            mode = "idle"
        else:
            mode = "active"

        # Ingest eBPF / Proc Fallback Telemetry events
        ebpf_events = []
        try:
            if os.path.exists("/tmp/snowos_ebpf_events.json"):
                with open("/tmp/snowos_ebpf_events.json") as f:
                    data = json.load(f)
                    ebpf_events = data.get("events", [])
        except Exception:
            pass

        return {
            "timestamp":     ts,
            "active_app":    win["title"],
            "window_title":  win["title"],
            "pid":           win["pid"],
            "wm_class":      win["wm_class"],
            "system_load":   telem["load_1min"],
            "mem_used_pct":  telem["mem_used_pct"],
            "battery":       telem["battery"],
            "mode":          mode,
            "iteration":     self._iteration,
            "ebpf_events":   ebpf_events,
        }

    def _predictive_prewarm(self, ctx: dict):
        """Predictive RAM Pre-Warming (Prefetching Page Cache)."""
        dev_apps = ["terminal", "code", "nvim", "vscode", "alacritty", "kitty", "konsole"]
        app_name = ctx.get("active_app", "").lower()
        
        is_dev_app = any(d in app_name for d in dev_apps)
        
        try:
            if os.path.exists("/tmp/snowos_profile.json"):
                with open("/tmp/snowos_profile.json") as f:
                    profile = json.load(f)
                    if profile.get("active_mode") in ["casual", "gaming"] and is_dev_app:
                        logger.info("Predictive pre-warming: Dev app focused while in Gaming mode. Pre-fetching workspace...")
                        # Run a background prefetch/vmtouch simulation
                        subprocess.Popen(["vmtouch", "-t", os.path.expanduser("~/")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            pass

    def run_once(self):
        """Run a single context cycle. Safe for --once CLI mode."""
        ctx = self._build_context()
        try:
            with open(CONTEXT_FILE, "w") as f:
                json.dump(ctx, f)
        except Exception as e:
            logger.warning(f"Context write failed: {e}")
        return ctx

    def run(self):
        logger.info("SnowOS Context Engine started.")

        def _stop_handler(sig, frame):
            logger.info("Context Engine shutting down...")
            self._stop.set()

        signal.signal(signal.SIGTERM, _stop_handler)
        signal.signal(signal.SIGINT, _stop_handler)

        while not self._stop.is_set():
            try:
                ctx = self.run_once()
                self._iteration += 1
                now = ctx["timestamp"]

                # Behavioral log (every BEHAVIOR_EVERY seconds)
                if now - self._last_behavior_ts >= BEHAVIOR_EVERY:
                    entry = {
                        "timestamp":    now,
                        "hour":         time.localtime(now).tm_hour,
                        "day_of_week":  time.localtime(now).tm_wday,
                        "active_app":   ctx["active_app"],
                        "window_title": ctx["window_title"],
                        "load":         ctx["system_load"],
                        "mode":         ctx["mode"],
                    }
                    append_behavior_log(entry)
                    self._last_behavior_ts = now

                # Visual context capture (every VISUAL_EVERY seconds)
                if now - self._last_visual_ts >= VISUAL_EVERY:
                    if capture_visual_context():
                        logger.debug("Visual context captured.")
                    self._last_visual_ts = now

                # Predictive RAM Pre-Warming check
                self._predictive_prewarm(ctx)

            except Exception as e:
                logger.error(f"Context engine cycle error: {e}")

            self._stop.wait(POLL_INTERVAL)

        logger.info("Context Engine stopped.")


# ── CLI Entry ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    engine = ContextEngine()
    if "--once" in sys.argv:
        ctx = engine.run_once()
        print(json.dumps(ctx, indent=2))
    else:
        engine.run()
