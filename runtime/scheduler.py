import threading
import time
import psutil
import logging
from .event_bus import bus

class RuntimeScheduler:
    """Orchestrates periodic system checks and module synchronization."""
    
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.logger = logging.getLogger("SnowOS.Scheduler")
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True, name="NyxRuntimeScheduler")
            self._thread.start()
            self.logger.info("Runtime Scheduler started.")

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._perform_sync()
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
            
            # Dynamic interval: more frequent if user is active
            interval = 5 if self.nyx.ui_state.state.get("user_state") == "active" else 15
            if self._stop_event.wait(interval):
                break

    def _perform_sync(self):
        # 1. System Health Check
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        bus.publish("system_health", {"cpu": cpu, "mem": mem})

        # 2. Memory Engine Sync (Predictions)
        if hasattr(self.nyx, "memory_engine"):
            prediction = self.nyx.memory_engine.predict_next_action()
            if prediction:
                bus.publish("ai_insight", {"prediction": prediction})

        # 3. Intent Awareness
        intent = self.nyx.ui_state.state.get("user_intent")
        if intent:
            bus.publish("user_intent", {"intent": intent})
