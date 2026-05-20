#!/usr/bin/env python3
import sys
import os
import signal

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib

class SnowOSGreeter(Gtk.Window):
    def __init__(self):
        super(SnowOSGreeter, self).__init__()
        
        # Configure the window for a fullscreen greeter
        self.set_default_size(1920, 1080)
        self.fullscreen()
        self.set_decorated(False)
        self.set_keep_above(True)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)
        
        # Setup WebKit Web View
        web_context = WebKit2.WebContext.get_default()
        web_context.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
        
        self.webview = WebKit2.WebView.new_with_context(web_context)
        
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_enable_webgl(True)
        settings.set_enable_html5_database(True)
        settings.set_enable_html5_local_storage(True)
        
        self.add(self.webview)
        
        # Load the local HTML file
        script_dir = os.path.dirname(os.path.realpath(__file__))
        html_path = os.path.join(script_dir, "ui", "index.html")
        uri = f"file://{html_path}"
        self.webview.load_uri(uri)
        
    def on_key_press(self, widget, event):
        # We can handle custom keybindings here if needed.
        # e.g., Esc to quit for debug, but disabled for production.
        return False

def main():
    # Handle sigint/sigterm
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = SnowOSGreeter()
    app.show_all()
    
    # Run the GTK main loop
    Gtk.main()

if __name__ == '__main__':
    main()
