#!/usr/bin/env python3
"""
SnowOS Frost Desktop — Upgraded with Frostbite Integration.

Components:
  - FrostTopPanel   : top bar with clock, AI status, battery
  - FrostDock       : bottom dock with app icons + Frostbite toggle
  - Frostbite       : glassmorphic AI companion sidebar (Super+F hotkey)
"""
import sys
import os
import time
import json
import subprocess
import threading
import logging

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, Gdk, GLib

logger = logging.getLogger("FrostDesktop")

# ── Local imports ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

try:
    from frostbite.frostbite_widget import FrostbiteWidget
    _FROSTBITE_AVAIL = True
except ImportError as e:
    logger.warning(f"Frostbite import failed: {e}")
    _FROSTBITE_AVAIL = False

CONTEXT_FILE  = "/tmp/snowos_context.json"
GOVERNOR_FILE = "/tmp/snowos_governor_state.json"


# ── CSS ───────────────────────────────────────────────────────────────────────
def _apply_css():
    provider = Gtk.CssProvider()
    # Prefer Frostbite CSS (superset of shell_theme.css)
    frostbite_css = os.path.join(_HERE, "frostbite", "frostbite_css.css")
    fallback_css  = os.path.join(_HERE, "shell_theme.css")
    for css_path in [frostbite_css, fallback_css]:
        if os.path.exists(css_path):
            try:
                provider.load_from_path(css_path)
                Gtk.StyleContext.add_provider_for_screen(
                    Gdk.Screen.get_default(), provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_USER,
                )
                return
            except Exception as e:
                logger.warning(f"CSS load failed ({css_path}): {e}")
    logger.warning("No CSS file found — proceeding without theming.")


# ── Context helpers ───────────────────────────────────────────────────────────
def _load_context() -> dict:
    try:
        with open(CONTEXT_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _load_governor() -> dict:
    try:
        with open(GOVERNOR_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _battery_str() -> str:
    """Read battery capacity from sysfs."""
    bat = "/sys/class/power_supply/BAT0"
    if os.path.exists(bat):
        try:
            cap    = open(f"{bat}/capacity").read().strip()
            status = open(f"{bat}/status").read().strip()
            icon   = "🔋" if status == "Discharging" else "⚡"
            return f"{icon} {cap}%"
        except Exception:
            pass
    return ""


# ── Top Panel ─────────────────────────────────────────────────────────────────
class FrostTopPanel(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_skip_taskbar_hint(True)

        screen = Gdk.Screen.get_default()
        self.set_size_request(screen.get_width(), 36)
        self.move(0, 0)
        self.set_keep_above(True)

        box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        box.get_style_context().add_class("frost-panel")

        # Left — SnowOS identity
        lbl_id = Gtk.Label(label="  ❄️  SnowOS")
        lbl_id.get_style_context().add_class("frost-panel")
        box.pack_start(lbl_id, False, False, 10)

        # Center — Clock
        self._lbl_clock = Gtk.Label()
        box.set_center_widget(self._lbl_clock)
        GLib.timeout_add_seconds(1, self._update_clock)
        self._update_clock()

        # Right — AI status + battery + governor mode
        self._lbl_status = Gtk.Label(label="[AI: Active]")
        self._lbl_status.get_style_context().add_class("frost-panel")
        box.pack_end(self._lbl_status, False, False, 10)

        self._lbl_battery = Gtk.Label(label="")
        self._lbl_battery.get_style_context().add_class("frost-panel")
        box.pack_end(self._lbl_battery, False, False, 4)

        self.add(box)
        GLib.timeout_add(3000, self._update_status)

    def _update_clock(self):
        self._lbl_clock.set_text(time.strftime("%H:%M  ·  %a %b %d"))
        return True

    def _update_status(self):
        ctx = _load_context()
        gov = _load_governor()
        prof = {}
        try:
            with open("/tmp/snowos_profile.json") as f:
                prof = json.load(f)
        except Exception:
            pass
        
        mode = prof.get("active_mode", "STUDENT").upper()
        profile = gov.get("power_profile", "balanced")
        load    = ctx.get("system_load", 0)
        status_text = f"[{mode}]  [AI: ❄️  Active]  [{profile.upper()}]  Load {load:.1f}"
        self._lbl_status.set_text(status_text)
        self._lbl_battery.set_text(_battery_str())
        return True


# ── Bottom Dock ───────────────────────────────────────────────────────────────
class FrostDock(Gtk.Window):
    _DOCK_APPS = [
        ("🌐", "Browser",   "xdg-open https://"),
        ("💻", "Terminal",  "x-terminal-emulator"),
        ("📁", "Files",     "nautilus"),
        ("⚙️",  "Settings",  "gnome-control-center"),
    ]

    def __init__(self, frostbite: "FrostbiteWidget | None" = None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)

        self._frostbite = frostbite

        screen = Gdk.Screen.get_default()
        width  = screen.get_width()
        height = screen.get_height()

        dock_w = 520 if not _FROSTBITE_AVAIL else 580
        self.set_size_request(dock_w, 68)
        self.move((width - dock_w) // 2, height - 82)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box   = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        box.get_style_context().add_class("frost-dock")
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # App launcher icons
        for icon, label, cmd in self._DOCK_APPS:
            btn = Gtk.Button(label=f"{icon}\n{label}")
            btn.get_style_context().add_class("frost-dock-icon")
            btn.connect("clicked", lambda _, c=cmd: self._launch(c))
            box.pack_start(btn, False, False, 2)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_start(4)
        sep.set_margin_end(4)
        box.pack_start(sep, False, False, 0)

        # Frostbite toggle button
        if _FROSTBITE_AVAIL:
            fb_btn = Gtk.Button(label="❄️\nFrostbite")
            fb_btn.get_style_context().add_class("frost-dock-icon")
            fb_btn.get_style_context().add_class("frostbite-btn")
            fb_btn.set_tooltip_text("Toggle Frostbite AI Companion (Super+F)")
            fb_btn.connect("clicked", lambda _: self._toggle_frostbite())
            box.pack_start(fb_btn, False, False, 2)

        outer.pack_start(box, True, True, 4)
        self.add(outer)

        self._current_mode = "student"
        GLib.timeout_add_seconds(1, self._update_visibility)

    def _update_visibility(self):
        try:
            with open("/tmp/snowos_profile.json") as f:
                prof = json.load(f)
                mode = prof.get("active_mode", "student")
                if mode != self._current_mode:
                    self._current_mode = mode
                    if mode in ["casual", "gaming"]:
                        self.hide()
                    else:
                        self.show_all()
        except Exception:
            pass
        return True

    def _launch(self, cmd: str):
        try:
            subprocess.Popen(cmd.split(), close_fds=True)
        except Exception as e:
            logger.warning(f"Launch failed ({cmd}): {e}")

    def _toggle_frostbite(self):
        if self._frostbite:
            self._frostbite.toggle()


# ── Global Hotkey Listener ────────────────────────────────────────────────────
def _start_hotkey_listener(frostbite_widget):
    """
    Listen for Super+F via XGrabKey / subprocess xbindkeys fallback.
    Uses a polling approach on /tmp/snowos_frostbite_toggle to avoid
    native keybinder dependency.
    """
    TOGGLE_FILE = "/tmp/snowos_frostbite_toggle"

    def _watch():
        last_mtime = 0
        while True:
            try:
                if os.path.exists(TOGGLE_FILE):
                    mtime = os.path.getmtime(TOGGLE_FILE)
                    if mtime != last_mtime:
                        last_mtime = mtime
                        GLib.idle_add(frostbite_widget.toggle)
            except Exception:
                pass
            time.sleep(0.3)

    t = threading.Thread(target=_watch, daemon=True, name="HotkeyWatcher")
    t.start()

    # Try to register Super+F via xbindkeys config
    xbindkeys_conf = os.path.expanduser("~/.xbindkeysrc.snowos")
    try:
        with open(xbindkeys_conf, "w") as f:
            f.write(f'"touch {TOGGLE_FILE}"\n  super + f\n')
        subprocess.Popen(["xbindkeys", "-f", xbindkeys_conf],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # xbindkeys may not be installed — file-poll still works


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=logging.INFO)
    _apply_css()

    # Instantiate Frostbite first (hidden)
    frostbite = None
    if _FROSTBITE_AVAIL:
        try:
            frostbite = FrostbiteWidget()
            # Do NOT show_all() — starts hidden
        except Exception as e:
            logger.error(f"Frostbite init failed: {e}")

    # Top panel
    panel = FrostTopPanel()
    panel.show_all()

    # Dock
    dock = FrostDock(frostbite=frostbite)
    dock.show_all()

    # Hotkey listener
    if frostbite:
        _start_hotkey_listener(frostbite)

    logger.info("Frost Desktop running. Frostbite: %s", "enabled" if frostbite else "disabled")
    Gtk.main()


if __name__ == "__main__":
    main()
