#!/usr/bin/env python3
"""
SnowOS WindowAI — Upgraded to read from Context Engine + Intent Governor.

Now uses real active-window context from /tmp/snowos_context.json and
governor predictions from /tmp/snowos_governor_state.json to propose
dynamic, context-aware window arrangements.
"""
import os
import json
import time
import logging

logger = logging.getLogger("SnowOS.WindowAI")

CONTEXT_FILE  = "/tmp/snowos_context.json"
GOVERNOR_FILE = "/tmp/snowos_governor_state.json"


def _load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


class WindowAI:
    """
    Intelligently manages window positioning and grouping.
    Reads real desktop context and governor predictions for proactive layout proposals.
    """

    def __init__(self):
        # Companion app pairings (keyword → companion)
        self.pairings = {
            "code":       "terminal",
            "vscode":     "terminal",
            "vim":        "terminal",
            "nvim":       "terminal",
            "browser":    "files",
            "firefox":    "files",
            "chromium":   "files",
            "gimp":       "files",
            "blender":    "terminal",
            "docker":     "terminal",
            "python":     "terminal",
            "slack":      "browser",
        }
        self._last_app: str = ""
        self._last_proposal_ts: float = 0.0

    def _publish(self, event_type: str, data: dict):
        """Publish via event bus (graceful fallback if bus unavailable)."""
        try:
            from runtime.event_bus import bus
            bus.publish(event_type, data)
        except Exception:
            logger.debug(f"WindowAI: event_bus unavailable — event {event_type}: {data}")

    def _get_active_app(self) -> str:
        """Read the active app from the real context engine output."""
        ctx = _load_json(CONTEXT_FILE)
        title = ctx.get("window_title", ctx.get("active_app", ""))
        if not title:
            return ""
        # Normalize to a keyword
        title_lower = title.lower()
        for keyword in self.pairings:
            if keyword in title_lower:
                return keyword
        # Return first word as best-effort app name
        return title_lower.split()[0] if title_lower.split() else ""

    def _get_predicted_apps(self) -> list:
        """Read predicted upcoming apps from the intent governor."""
        gov = _load_json(GOVERNOR_FILE)
        return gov.get("predicted_apps", [])

    def propose_arrangement_for(self, app_name: str = ""):
        """
        Propose the best layout for the current or given application.
        If app_name is empty, reads from the live context engine.
        Rate-limited: fires at most once per 10 seconds.
        """
        now = time.time()
        if now - self._last_proposal_ts < 10:
            return  # Rate-limit proposals
        self._last_proposal_ts = now

        if not app_name:
            app_name = self._get_active_app()

        if not app_name:
            return

        # Skip if same app as last time (no change)
        if app_name == self._last_app:
            return
        self._last_app = app_name

        companion = self.pairings.get(app_name)

        # Also hint at predicted apps from governor
        predicted = self._get_predicted_apps()

        if companion:
            logger.info(f"WindowAI: Proposing split-view for {app_name} + {companion}")
            self._publish("ui_window_update", {
                "type":      "arrangement",
                "layout":    "split",
                "apps":      [app_name, companion],
                "predicted": predicted,
                "source":    "window_ai_context",
            })
        else:
            logger.info(f"WindowAI: Proposing focus-mode for {app_name}")
            self._publish("ui_window_update", {
                "type":      "arrangement",
                "layout":    "focus",
                "apps":      [app_name],
                "predicted": predicted,
                "source":    "window_ai_context",
            })

    def update_active_app(self, data: dict = None):
        """Called by the event bus on window change events."""
        app = ""
        if data:
            app = data.get("app", data.get("active_app", ""))
        self.propose_arrangement_for(app)

    def get_layout_suggestion(self) -> dict:
        """
        Return the current layout suggestion without publishing.
        Useful for querying by Frostbite or the overlay.
        """
        app = self._get_active_app()
        predicted = self._get_predicted_apps()
        companion = self.pairings.get(app)
        return {
            "active_app": app,
            "companion":  companion,
            "layout":     "split" if companion else "focus",
            "predicted":  predicted,
        }
