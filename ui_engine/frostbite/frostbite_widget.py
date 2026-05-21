#!/usr/bin/env python3
"""
Frostbite Widget — Native SnowOS Chatbot Companion.

A glassmorphic GTK3 sidebar that slides in from the right edge,
providing direct hardware control and AI conversation via snowos-broker.

Architecture:
  User NL input → Intent parser → FrostbiteControlBridge (direct HW API)
                               → Nyx broker (AI reasoning for complex queries)
                               → PseudoTerminalBridge (dev environment setup)
"""
import os
import sys
import json
import time
import socket
import logging
import threading

import gi
gi.require_version("Gtk",  "3.0")
gi.require_version("Gdk",  "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, Gdk, GLib, Pango

# ── Local imports ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_UI_ENGINE = os.path.dirname(_HERE)
sys.path.insert(0, _UI_ENGINE)

from frostbite.control_bridge import FrostbiteControlBridge
from frostbite.pty_bridge import PseudoTerminalBridge, notify

logger = logging.getLogger("Frostbite")

RUNTIME_DIR  = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
CONTEXT_FILE = "/tmp/snowos_context.json"
BROKER_SOCK  = os.path.join(RUNTIME_DIR, "broker.sock")

_CSS_PATH = os.path.join(_HERE, "frostbite_css.css")

# ── Quick-action pills ────────────────────────────────────────────────────────
_QUICK_ACTIONS = [
    ("⚡ Kill hog",      "kill whatever is hogging my battery"),
    ("🔇 Mute all",     "mute everything"),
    ("🎵 Mute except ♪","mute everything except music"),
    ("🔋 Battery",      "battery status"),
    ("📊 System",       "system summary"),
    ("🌐 WiFi",         "toggle wifi"),
]

# ── Intent keyword router ─────────────────────────────────────────────────────
_INTENT_KEYWORDS = {
    "kill_hog":          ["kill", "hog", "battery", "drain", "cpu hogging"],
    "volume_mute":       ["mute everything", "mute all", "silence", "quiet"],
    "mute_except_music": ["mute except music", "mute all except", "keep music"],
    "volume_unmute":     ["unmute", "sound on", "audio on"],
    "volume_set":        ["volume", "set volume", "turn volume"],
    "brightness_set":    ["brightness", "dim screen", "brighter"],
    "wifi_toggle":       ["toggle wifi", "turn wifi", "wifi on", "wifi off"],
    "network_status":    ["network", "connection", "internet"],
    "battery_status":    ["battery", "charge", "power"],
    "system_summary":    ["system", "status", "summary", "how is"],
    "process_list":      ["processes", "running apps", "what's running"],
    "screenshot":        ["screenshot", "capture screen"],
}


def _parse_intent(text: str) -> tuple:
    """
    Return (intent_name, params_dict) from free-form user text.
    Falls back to ('none', {}) if no match.
    """
    lower = text.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            params = {}
            # Extract level for volume/brightness
            import re
            m = re.search(r"\b(\d+)\b", text)
            if m:
                params["level"] = int(m.group(1))
            return intent, params
    return "none", {}


def _load_context() -> dict:
    try:
        with open(CONTEXT_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _ask_broker_nyx(user_text: str, context: dict) -> str:
    """
    Send the user's query to the Nyx broker for AI reasoning.
    Returns a text response or error message.
    """
    if not os.path.exists(BROKER_SOCK):
        return None
    try:
        payload = json.dumps({
            "source_id":       "frostbite",
            "target_resource": "nyx_ai",
            "action":          "chat",
            "context":         json.dumps(context)[:512],
            "query":           user_text[:1024],
        })
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(8.0)
        s.connect(BROKER_SOCK)
        s.sendall(payload.encode())
        resp = s.recv(32768)
        s.close()
        data = json.loads(resp.decode())
        return data.get("response") or data.get("reason") or str(data)
    except Exception as e:
        return None


# ── Message Widget ────────────────────────────────────────────────────────────
class MessageBubble(Gtk.Box):
    def __init__(self, text: str, role: str = "assistant", timestamp: str = None):
        """
        role: 'user' | 'assistant' | 'system_event' | 'error'
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.set_margin_start(12)
        self.set_margin_end(12)

        bubble = Gtk.Label(label=text)
        bubble.set_line_wrap(True)
        bubble.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        bubble.set_max_width_chars(45)
        bubble.set_xalign(1.0 if role == "user" else 0.0)
        bubble.get_style_context().add_class("message-bubble")
        bubble.get_style_context().add_class(role)

        if role == "user":
            self.set_halign(Gtk.Align.END)
        elif role == "system_event":
            self.set_halign(Gtk.Align.CENTER)
        else:
            self.set_halign(Gtk.Align.START)

        self.pack_start(bubble, False, False, 0)

        if timestamp and role in ("user", "assistant"):
            ts_label = Gtk.Label(label=timestamp)
            ts_label.get_style_context().add_class("message-timestamp")
            ts_label.set_xalign(1.0 if role == "user" else 0.0)
            self.pack_start(ts_label, False, False, 0)


# ── Main Frostbite Widget ─────────────────────────────────────────────────────
class FrostbiteWidget(Gtk.Window):
    WIDTH = 420

    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        self.control = FrostbiteControlBridge()
        self.pty     = PseudoTerminalBridge()
        self._visible = False
        self._thinking = False

        self._apply_css()
        self._position_sidebar()
        self._build_ui()

        self.connect("key-press-event", self._on_key)
        GLib.timeout_add(3000, self._update_context_ribbon)

    # ── CSS ───────────────────────────────────────────────────────────────────
    def _apply_css(self):
        provider = Gtk.CssProvider()
        if os.path.exists(_CSS_PATH):
            provider.load_from_path(_CSS_PATH)
        else:
            # Inline minimal fallback
            provider.load_from_data(b"""
                .frostbite-window { background: rgba(8,10,22,0.95); }
                .frostbite-header { background: rgba(0,60,140,0.3); padding: 12px; }
                .frostbite-title  { color: #ddeeff; font-weight: bold; font-size: 14px; }
                .message-bubble   { border-radius: 10px; padding: 8px 12px; }
                .message-bubble.user { background: rgba(0,100,200,0.35); color: #ddeeff; }
                .message-bubble.assistant { background: rgba(255,255,255,0.05); color: #c0d8ff; }
                .frostbite-entry  { background: rgba(255,255,255,0.07); border-radius: 18px;
                                    color: #ddeeff; padding: 7px 14px; border: 1px solid rgba(80,140,255,0.25); }
                .send-button      { background: #0060cc; border-radius: 50%; color: #fff;
                                    min-width: 36px; min-height: 36px; }
                .frost-dock { background: rgba(5,8,25,0.88); border-radius: 16px; }
                .frost-dock-icon  { background: rgba(255,255,255,0.06); border-radius: 10px;
                                    color: #a0c0ff; min-width: 50px; min-height: 50px; }
            """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
        self.get_style_context().add_class("frostbite-window")

    # ── Positioning ───────────────────────────────────────────────────────────
    def _position_sidebar(self):
        screen = Gdk.Screen.get_default()
        height = screen.get_height()
        width  = screen.get_width()
        self.set_size_request(self.WIDTH, height)
        self.move(width - self.WIDTH, 0)

    # ── UI Build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.get_style_context().add_class("frostbite-window")

        # ── Header ────────────────────────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.get_style_context().add_class("frostbite-header")
        header.set_margin_start(4)
        header.set_margin_end(4)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_title = Gtk.Label(label="❄️  Frostbite")
        lbl_title.get_style_context().add_class("frostbite-title")
        lbl_title.set_xalign(0)
        lbl_sub = Gtk.Label(label="SNOWOS AI COMPANION")
        lbl_sub.get_style_context().add_class("frostbite-subtitle")
        lbl_sub.set_xalign(0)
        title_box.pack_start(lbl_title, False, False, 0)
        title_box.pack_start(lbl_sub,   False, False, 0)

        self._status_badge = Gtk.Label(label="● READY")
        self._status_badge.get_style_context().add_class("status-badge")

        close_btn = Gtk.Button(label="✕")
        close_btn.get_style_context().add_class("header-btn")
        close_btn.connect("clicked", lambda _: self.hide_sidebar())

        header.pack_start(title_box,          True,  True,  0)
        header.pack_start(self._status_badge, False, False, 0)
        header.pack_start(close_btn,          False, False, 0)

        # ── Context Ribbon ─────────────────────────────────────────────────
        self._ctx_ribbon = Gtk.Label(label="Context: scanning...")
        self._ctx_ribbon.get_style_context().add_class("context-label")
        self._ctx_ribbon.set_xalign(0)
        ctx_box = Gtk.Box()
        ctx_box.get_style_context().add_class("context-ribbon")
        ctx_box.add(self._ctx_ribbon)

        # ── Quick Action Pills ─────────────────────────────────────────────
        pills_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        pills_box.get_style_context().add_class("quick-actions")
        pills_flow = Gtk.FlowBox()
        pills_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        pills_flow.set_max_children_per_line(3)
        pills_flow.set_homogeneous(False)
        for label, prompt in _QUICK_ACTIONS:
            pill = Gtk.Button(label=label)
            pill.get_style_context().add_class("quick-pill")
            pill.connect("clicked", lambda _, p=prompt: self._submit(p))
            pills_flow.add(pill)
        pills_box.pack_start(pills_flow, True, True, 0)

        # ── Chat Area ──────────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.get_style_context().add_class("chat-scroll")
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self._chat_list = Gtk.ListBox()
        self._chat_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._chat_list.set_activate_on_single_click(False)
        scroll.add(self._chat_list)
        self._scroll = scroll

        # ── Input Area ────────────────────────────────────────────────────
        input_area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_area.get_style_context().add_class("input-area")
        input_area.set_margin_start(4)
        input_area.set_margin_end(4)
        input_area.set_margin_top(4)
        input_area.set_margin_bottom(4)

        self._entry = Gtk.Entry()
        self._entry.set_placeholder_text("Ask anything, or say 'kill battery hog'...")
        self._entry.get_style_context().add_class("frostbite-entry")
        self._entry.set_hexpand(True)
        self._entry.connect("activate", lambda _: self._on_send())

        send_btn = Gtk.Button(label="➤")
        send_btn.get_style_context().add_class("send-button")
        send_btn.connect("clicked", lambda _: self._on_send())

        input_area.pack_start(self._entry,  True,  True,  0)
        input_area.pack_start(send_btn,     False, False, 0)

        # ── Assembly ───────────────────────────────────────────────────────
        root.pack_start(header,     False, False, 0)
        root.pack_start(ctx_box,    False, False, 0)
        root.pack_start(pills_box,  False, False, 0)
        root.pack_start(scroll,     True,  True,  0)
        root.pack_start(input_area, False, False, 0)
        self.add(root)

        # Welcome message
        self._add_message(
            "❄️  Hey! I'm Frostbite — your SnowOS companion. I can control your "
            "system, help with development, and answer questions. Try a quick action above!",
            role="assistant",
        )

    # ── Chat Logic ────────────────────────────────────────────────────────────
    def _add_message(self, text: str, role: str = "assistant"):
        ts = time.strftime("%H:%M")
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        row.set_selectable(False)
        bubble = MessageBubble(text, role=role, timestamp=ts if role != "system_event" else None)
        row.add(bubble)
        GLib.idle_add(self._append_row, row)

    def _append_row(self, row):
        self._chat_list.add(row)
        self._chat_list.show_all()
        # Scroll to bottom
        adj = self._scroll.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper() - adj.get_page_size()))
        return False

    def _set_status(self, text: str, thinking: bool = False):
        def _update():
            self._status_badge.set_label(text)
            ctx = self._status_badge.get_style_context()
            if thinking:
                ctx.add_class("thinking")
            else:
                ctx.remove_class("thinking")
            return False
        GLib.idle_add(_update)

    def _on_send(self):
        text = self._entry.get_text().strip()
        if not text:
            return
        self._entry.set_text("")
        self._add_message(text, role="user")
        threading.Thread(target=self._process_input, args=(text,), daemon=True).start()

    def _submit(self, prompt: str):
        """Submit a pre-canned quick action prompt."""
        self._entry.set_text(prompt)
        self._on_send()

    def _process_input(self, text: str):
        self._set_status("● THINKING", thinking=True)

        # 1. Try local intent routing first (fast path)
        intent, params = _parse_intent(text)

        if intent != "none":
            result = self.control.execute_intent(intent, params)
            GLib.idle_add(self._add_message, result, "assistant")
            self._set_status("● READY")
            return

        # 2. Check for dev-environment setup request
        dev_keywords = ["set up", "install", "setup", "create environment",
                        "configure", "install packages", "pip install", "apt install"]
        lower = text.lower()
        if any(kw in lower for kw in dev_keywords):
            self._run_dev_task(text)
            return

        # 3. Forward to Nyx broker for AI reasoning
        ctx = _load_context()
        response = _ask_broker_nyx(text, ctx)
        if response:
            GLib.idle_add(self._add_message, response, "assistant")
        else:
            # Fallback: helpful default
            GLib.idle_add(
                self._add_message,
                "I can help with system control, file search, and development tasks. "
                "Try: 'kill battery hog', 'mute everything except music', "
                "'set volume to 60', or 'system summary'.",
                "assistant",
            )
        self._set_status("● READY")

    def _run_dev_task(self, task_description: str):
        """Spawn a PTY to execute a dev environment task."""
        self._add_message(
            f"🖥️  Starting dev task: {task_description[:80]}...\n"
            "Spawning terminal bridge — I'll notify you when done.",
            "system_event",
        )

        # Build a command from the task description
        # Very simple heuristic: if it mentions packages, run apt/pip
        import re
        packages = re.findall(r"\b([a-z][a-z0-9_-]{1,30})\b", task_description.lower())
        if "pip" in task_description.lower():
            cmd = f"pip3 install --user {' '.join(packages[:5])}"
        elif "apt" in task_description.lower() or "install" in task_description.lower():
            cmd = f"sudo apt-get install -y {' '.join(packages[:5])}"
        else:
            cmd = f"bash -c '{task_description}'"

        progress_lines = []

        def _on_progress(line, pct):
            if line.strip():
                progress_lines.append(line)
                if len(progress_lines) % 5 == 0:
                    snippet = "\n".join(progress_lines[-3:])
                    GLib.idle_add(
                        self._add_message,
                        f"```\n{snippet}\n```",
                        "system_event",
                    )

        def _on_complete(success, output):
            if success:
                msg = "✅ Dev task completed successfully!"
                notify("Frostbite", "Dev environment ready!", "dialog-information")
            else:
                msg = "⚠️ Dev task finished with errors. Check the output above."
                notify("Frostbite", "Dev task had errors.", "dialog-warning")
            GLib.idle_add(self._add_message, msg, "assistant")
            self._set_status("● READY")

        self.pty.run_command(cmd, on_progress=_on_progress, on_complete=_on_complete)

    # ── Context Ribbon ────────────────────────────────────────────────────────
    def _update_context_ribbon(self):
        ctx = _load_context()
        app   = ctx.get("active_app", "Idle")
        load  = ctx.get("system_load", 0)
        mode  = ctx.get("mode", "active")
        label = f"👁 {app[:40]}  ·  Load {load:.1f}  ·  {mode}"
        self._ctx_ribbon.set_label(label)
        return True  # repeat

    # ── Show / Hide (slide animation) ─────────────────────────────────────────
    def show_sidebar(self):
        if not self._visible:
            self.show_all()
            self._visible = True
            self._entry.grab_focus()

    def hide_sidebar(self):
        if self._visible:
            self.hide()
            self._visible = False

    def toggle(self):
        if self._visible:
            self.hide_sidebar()
        else:
            self.show_sidebar()

    # ── Key handler ───────────────────────────────────────────────────────────
    def _on_key(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide_sidebar()
            return True
        return False


# ── Standalone launch ─────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=logging.INFO)
    widget = FrostbiteWidget()
    widget.show_all()
    widget._visible = True
    Gtk.main()


if __name__ == "__main__":
    main()
