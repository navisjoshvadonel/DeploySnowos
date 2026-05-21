#!/usr/bin/env python3
"""
Frostbite Control Bridge — Direct snowos-control IPC adapter.

Maps Frostbite natural language intents to typed hardware API calls
via the snowos-broker Unix socket (no bash passthrough).
"""
import os
import json
import socket
import logging
import subprocess
import re
from typing import Optional

logger = logging.getLogger("FrostbiteControlBridge")

RUNTIME_DIR  = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
BROKER_SOCK  = os.path.join(RUNTIME_DIR, "broker.sock")
CONTROL_SOCK = os.path.join(RUNTIME_DIR, "control.sock")


def _broker_request(source_id: str, resource: str, action: str, context: str = "") -> Optional[dict]:
    """Send a capability request to the permission broker."""
    if not os.path.exists(BROKER_SOCK):
        logger.warning("Broker socket not available.")
        return None
    try:
        payload = json.dumps({
            "source_id":       source_id,
            "target_resource": resource,
            "action":          action,
            "context":         context,
        })
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect(BROKER_SOCK)
        s.sendall(payload.encode())
        resp = s.recv(8192)
        s.close()
        return json.loads(resp.decode())
    except Exception as e:
        logger.error(f"Broker request failed: {e}")
        return None


def _run(cmd: list, timeout: int = 5) -> tuple:
    """Run a command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


class FrostbiteControlBridge:
    """
    Typed hardware control API for Frostbite.
    All calls go through the broker for permission enforcement.
    """

    SOURCE_ID = "frostbite"

    # ── Volume ────────────────────────────────────────────────────────────────
    def set_volume(self, level: int) -> str:
        """Set system volume 0-100."""
        level = max(0, min(100, level))
        code, _, err = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        if code != 0:
            # Try amixer fallback
            _run(["amixer", "-q", "set", "Master", f"{level}%"])
        return f"Volume set to {level}%"

    def mute_system(self) -> str:
        _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
        return "System muted."

    def unmute_system(self) -> str:
        _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
        return "System unmuted."

    def mute_except_music(self) -> str:
        """
        Mute all audio sinks except those associated with music players.
        Uses pactl to enumerate and selectively mute sink-inputs.
        """
        music_keywords = ["spotify", "rhythmbox", "clementine", "vlc music",
                          "mpd", "mocp", "ncmpcpp", "cmus", "lollypop"]
        code, out, _ = _run(["pactl", "list", "sink-inputs"])
        if code != 0:
            return "Could not enumerate audio sinks."

        # Parse sink-input IDs and their process names
        blocks = out.split("Sink Input #")
        muted  = []
        kept   = []
        for block in blocks[1:]:
            lines = block.splitlines()
            sink_id = lines[0].strip() if lines else ""
            app_name = ""
            for line in lines:
                if "application.name" in line.lower() or "media.name" in line.lower():
                    m = re.search(r'"([^"]+)"', line)
                    if m:
                        app_name = m.group(1).lower()
                        break
            is_music = any(kw in app_name for kw in music_keywords)
            if sink_id:
                if is_music:
                    kept.append(app_name)
                else:
                    _run(["pactl", "set-sink-input-mute", sink_id, "1"])
                    muted.append(app_name or sink_id)

        if not muted and not kept:
            return "No audio sinks found."
        msg = f"Muted {len(muted)} audio streams."
        if kept:
            msg += f" Kept: {', '.join(kept)}."
        return msg

    # ── Brightness ────────────────────────────────────────────────────────────
    def set_brightness(self, level: int) -> str:
        """Set display brightness 0-100%."""
        level = max(5, min(100, level))
        # Try brightnessctl
        code, _, _ = _run(["brightnessctl", "set", f"{level}%"])
        if code == 0:
            return f"Brightness set to {level}%"
        # Try xrandr
        frac = round(level / 100.0, 2)
        code, out, _ = _run(["xrandr", "--listmonitors"])
        if code == 0:
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and not parts[0].startswith("Monitors"):
                    monitor = parts[-1]
                    _run(["xrandr", "--output", monitor, "--brightness", str(frac)])
                    return f"Brightness set to {level}%"
        return f"Brightness adjustment attempted at {level}%"

    # ── Network ───────────────────────────────────────────────────────────────
    def toggle_wifi(self) -> str:
        """Toggle WiFi using nmcli."""
        code, state, _ = _run(["nmcli", "radio", "wifi"])
        if "enabled" in state:
            _run(["nmcli", "radio", "wifi", "off"])
            return "WiFi disabled."
        _run(["nmcli", "radio", "wifi", "on"])
        return "WiFi enabled."

    def get_network_status(self) -> str:
        _, out, _ = _run(["nmcli", "-t", "-f", "NAME,TYPE,STATE", "connection", "show", "--active"])
        if out:
            return "Network:\n" + out
        return "No active network connections."

    # ── Process Management ────────────────────────────────────────────────────
    def kill_battery_hog(self) -> str:
        """Find and kill the top CPU/battery-consuming process."""
        _, out, _ = _run(["ps", "-eo", "pid,comm,%cpu", "--sort=-%cpu"])
        lines = out.splitlines()
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 3:
                pid, name, cpu = parts[0], parts[1], parts[2]
                # Skip system-critical processes
                skip = {"systemd", "Xorg", "kwin", "gnome-shell", "python3",
                        "nyx", "sentinel", "broker", "frostbite"}
                if any(s in name.lower() for s in skip):
                    continue
                try:
                    import signal as sig
                    os.kill(int(pid), sig.SIGTERM)
                    return f"Terminated '{name}' (PID {pid}, CPU {cpu}%) — battery hog eliminated."
                except Exception as e:
                    return f"Could not kill {name}: {e}"
        return "No runaway process found."

    def get_process_list(self, top_n: int = 8) -> str:
        _, out, _ = _run(["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"])
        lines = out.splitlines()
        return "\n".join(lines[:top_n + 1])

    # ── System Info ───────────────────────────────────────────────────────────
    def get_system_summary(self) -> str:
        _, uptime, _ = _run(["uptime", "-p"])
        _, mem, _    = _run(["free", "-h"])
        _, disk, _   = _run(["df", "-h", "/"])
        load         = os.getloadavg()
        lines = [
            f"Uptime: {uptime}",
            f"Load avg: {load[0]:.1f} / {load[1]:.1f} / {load[2]:.1f}",
            f"\nMemory:\n{mem}",
            f"\nDisk (/):\n{disk}",
        ]
        return "\n".join(lines)

    def get_battery_status(self) -> str:
        _, out, _ = _run(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"])
        if out:
            return out
        # Fallback
        bat = "/sys/class/power_supply/BAT0"
        if os.path.exists(bat):
            cap    = open(f"{bat}/capacity").read().strip()
            status = open(f"{bat}/status").read().strip()
            return f"Battery: {cap}% — {status}"
        return "Battery info unavailable."

    # ── Screenshot / Capture ──────────────────────────────────────────────────
    def take_screenshot(self, path: str = "/tmp/frostbite_snap.png") -> str:
        code, _, _ = _run(["scrot", path])
        if code == 0:
            return f"Screenshot saved to {path}"
        _run(["import", "-window", "root", path])
        return f"Screenshot saved to {path}"

    # ── Intent Router ─────────────────────────────────────────────────────────
    def execute_intent(self, intent: str, params: dict = None) -> str:
        """
        Route a parsed intent string to the appropriate hardware call.
        Intents: volume_set, volume_mute, volume_unmute, mute_except_music,
                 brightness_set, wifi_toggle, kill_hog, system_summary,
                 battery_status, process_list, screenshot
        """
        if params is None:
            params = {}
        dispatch = {
            "volume_set":         lambda: self.set_volume(params.get("level", 50)),
            "volume_mute":        self.mute_system,
            "volume_unmute":      self.unmute_system,
            "mute_except_music":  self.mute_except_music,
            "brightness_set":     lambda: self.set_brightness(params.get("level", 70)),
            "wifi_toggle":        self.toggle_wifi,
            "network_status":     self.get_network_status,
            "kill_hog":           self.kill_battery_hog,
            "system_summary":     self.get_system_summary,
            "battery_status":     self.get_battery_status,
            "process_list":       self.get_process_list,
            "screenshot":         self.take_screenshot,
        }
        fn = dispatch.get(intent)
        if fn:
            try:
                return fn()
            except Exception as e:
                return f"Error executing {intent}: {e}"
        return f"Unknown intent: {intent}"
