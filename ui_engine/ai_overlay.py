#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import json

class AIOverlay(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_keep_above(True)
        
        self.fullscreen()
        
        # Main layout container
        overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay_box.get_style_context().add_class("ai-overlay-bg")
        self.add(overlay_box)
        
        # Center container
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_halign(Gtk.Align.CENTER)
        
        # Greeting
        lbl_greet = Gtk.Label(label="How can I assist you?")
        lbl_greet.get_style_context().add_class("ai-text-primary")
        center_box.pack_start(lbl_greet, False, False, 0)
        
        # Context info
        self.lbl_context = Gtk.Label(label="Context: Scanning...")
        self.lbl_context.get_style_context().add_class("ai-text-secondary")
        center_box.pack_start(self.lbl_context, False, False, 0)
        
        # Input Field
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Type a command, ask a question, or request a layout change...")
        self.entry.get_style_context().add_class("ai-prompt-box")
        self.entry.set_width_chars(60)
        self.entry.connect("activate", self.on_submit)
        center_box.pack_start(self.entry, False, False, 20)
        
        overlay_box.pack_start(center_box, True, True, 0)
        
        # Allow Esc to close
        self.connect("key-press-event", self.on_key_press)
        
        GLib.timeout_add(1000, self.update_context)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide_overlay()
            return True
        return False
        
    def on_submit(self, widget):
        cmd = self.entry.get_text()
        print(f"User requested: {cmd}")
        self.entry.set_text("")
        self.hide_overlay()
        
    def hide_overlay(self):
        print("Hiding AI Overlay")
        self.hide()
        # Clean exit for prototype
        Gtk.main_quit()
        
    def update_context(self):
        try:
            with open("/tmp/snowos_context.json", "r") as f:
                data = json.load(f)
                active_app = data.get("active_app", "None")
                self.lbl_context.set_text(f"Context: Looking at {active_app}")
        except Exception:
            self.lbl_context.set_text("Context: Idle")
        return True

def apply_css():
    css_provider = Gtk.CssProvider()
    css_path = os.path.join(os.path.dirname(__file__), "shell_theme.css")
    if os.path.exists(css_path):
        css_provider.load_from_path(css_path)
        screen = Gdk.Screen.get_default()
        context = Gtk.StyleContext()
        context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    else:
        print("CSS file missing, proceeding without theming.")

def main():
    apply_css()
    overlay = AIOverlay()
    overlay.show_all()
    print("AI Overlay ready. (Press Esc to hide)")
    Gtk.main()

if __name__ == '__main__':
    main()
