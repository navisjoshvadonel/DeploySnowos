import os
import json
import psutil
import time
from threading import Thread, Event

class UIStateController:
    """The 'Brain' of the SnowOS UI.
    Tracks focus levels, system stress, and user intent.
    """
    def __init__(self, state_file=None, on_intent_change=None):
        self.on_intent_change = on_intent_change
        self.state_file = state_file or os.path.expanduser("~/snowos/nyx/ui_state.json")
        self.state = {
            "focus_level": "active", # idle, active, power, dev
            "system_stress": 0.0,    # 0.0 to 1.0
            "user_intent": "coding", # coding, browsing, media, idle
            "last_interaction": time.time(),
            "predicted_next_app": None,
            "performance_mode": "balanced", # low_power, balanced, high_performance
            "ai_active": False,
            "aesthetic_tokens": ["frosted", "balanced"]
        }
        self._stop_event = Event()
        self._thread = None
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state.update(json.load(f))
            except Exception:
                pass

    def _save(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception:
            pass

    def start(self):
        if not self._thread:
            # Stage 50: Event-driven UI Bridge
            from runtime.event_bus import bus
            bus.subscribe("ui_mode_change", self._on_mode_change)
            
            self._thread = Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()

    def _on_mode_change(self, mode):
        """Handle mode changes triggered by the Runtime Controller."""
        self.state["performance_mode"] = mode
        # Regenerate tokens to reflect the new mode (e.g., 'performance' mode trims effects)
        self.state["aesthetic_tokens"] = self._generate_aesthetic_tokens()
        self._save()

    def stop(self):
        self._stop_event.set()

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            self._update_system_stress()
            self._infer_user_intent()
            self._update_focus_level()
            self._update_personality()
            self.state["aesthetic_tokens"] = self._generate_aesthetic_tokens()
            self._save()
            self._stop_event.wait(2)

    def _update_system_stress(self):
        cpu = psutil.cpu_percent(interval=None) / 100.0
        ram = psutil.virtual_memory().percent / 100.0
        # Weighted average for stress
        self.state["system_stress"] = (cpu * 0.7) + (ram * 0.3)

    def _infer_user_intent(self):
        """Scan running processes to guess what the user is doing."""
        old_intent = self.state["user_intent"]
        try:
            # We look for signatures of common workloads
            proc_names = [p.name().lower() for p in psutil.process_iter(['name'])]
            
            if any(name in ["gcc", "g++", "make", "python", "node", "code", "cargo"] for name in proc_names):
                self.state["user_intent"] = "coding"
            elif any(name in ["vlc", "mpv", "spotify", "discord"] for name in proc_names):
                self.state["user_intent"] = "media"
            elif any(name in ["firefox", "chrome", "brave"] for name in proc_names):
                self.state["user_intent"] = "browsing"
            else:
                self.state["user_intent"] = "idle"
        except Exception:
            pass

        if self.state["user_intent"] != old_intent and self.on_intent_change:
            self.on_intent_change(self.state["user_intent"])

    def _update_focus_level(self):
        idle_time = time.time() - self.state["last_interaction"]
        if idle_time > 300: # 5 minutes
            self.state["focus_level"] = "idle"
        elif self.state["system_stress"] > 0.8:
            self.state["focus_level"] = "power"
        else:
            self.state["focus_level"] = "active"

    def set_intent(self, intent):
        self.state["user_intent"] = intent
        self.state["last_interaction"] = time.time()
        self._save()

    def _update_personality(self):
        """Adjust the OS 'personality' based on system health and history."""
        stress = self.state["system_stress"]
        if stress > 0.8:
            self.state["mood"] = "protective" # Focus on stability
        elif stress < 0.2:
            self.state["mood"] = "creative"   # Suggest new features/improvements
        else:
            self.state["mood"] = "efficient"  # Focus on workflow

    def _generate_aesthetic_tokens(self):
        """Generate tokens that describe the visual state based on stress and mood."""
        stress = self.state["system_stress"]
        mood = self.state.get("mood", "efficient")
        
        tokens = [mood]
        if stress > 0.8:
            tokens += ["high_stress", "thaw", "vibrant"]
        elif stress < 0.2:
            tokens += ["idle", "deep_freeze", "ambient"]
        else:
            tokens += ["active", "frosted", "balanced"]
        return tokens

    def get_ui_context(self):
        """Returns a snapshot for the GNOME extension."""
        return {
            "focus": self.state["focus_level"],
            "stress": self.state["system_stress"],
            "intent": self.state["user_intent"],
            "perf": self.state["performance_mode"],
            "tokens": self.state["aesthetic_tokens"],
            "mood": self.state.get("mood", "efficient")
        }
