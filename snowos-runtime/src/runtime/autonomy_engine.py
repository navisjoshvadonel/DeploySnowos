"""
SnowOS Runtime — AutonomyEngine
================================
Extracted from nyx.py (Stage 29).

The AutonomyEngine runs as a background thread. When the system is idle
(no active workers), it queries the LLM with recent failure events and
reflection insights to determine if a proactive goal should be submitted.

It is rate-limited to max_auto_tasks_per_hour to prevent runaway AI action.
All decisions are logged to autonomy.log for human review.
"""

import os
import re
import json
import time
import threading
import datetime
import logging

logger = logging.getLogger("SnowOS.AutonomyEngine")


class AutonomyEngine:
    """
    Proactive AI decision loop.

    When idle, queries the Nyx LLM with system context and may issue
    new goals automatically. Requires explicit opt-in via:
        config["autonomy_enabled"] = True
    """

    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.enabled = self.nyx.config.get("autonomy_enabled", False)
        self.log_file = os.path.join(self.nyx.log_dir, "autonomy.log")
        self.last_run = 0
        self.task_count_hour = 0
        self.last_hour_reset = time.time()
        self.failed_goals: dict[str, int] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self):
        """Start the background autonomy loop."""
        if not self._thread or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop, daemon=True, name="NyxAutonomy"
            )
            self._thread.start()
            logger.info("AutonomyEngine: Started (enabled=%s).", self.enabled)

    def stop(self):
        """Signal the autonomy loop to stop."""
        self._stop_event.set()

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop_event.is_set():
            if self.enabled and len(self.nyx.scheduler_engine.active_workers) == 0:
                self._think()
            self._stop_event.wait(10)

    def _think(self):
        """Evaluate system state and propose a proactive action if warranted."""
        # Rate limiting
        if time.time() - self.last_hour_reset > 3600:
            self.task_count_hour = 0
            self.last_hour_reset = time.time()

        max_tasks = self.nyx.config.get("max_auto_tasks_per_hour", 50)
        if self.task_count_hour >= max_tasks:
            return

        # Gather context
        failures = [
            n for n in self.nyx.emg.graph["nodes"].values()
            if isinstance(n, dict) and n.get("type") == "failure_event"
        ]
        insights = getattr(self.nyx, "reflection", None)
        insights_data = getattr(insights, "insights", []) if insights else []

        prompt = (
            "You are the Autonomy Executive of SnowOS.\n"
            "System state: Idle.\n"
            f"Recent Failures: {failures[-3:] if failures else 'None'}\n"
            f"Insights: {insights_data[:3] if insights_data else 'None'}\n\n"
            "Should we take any proactive action? If so, return JSON: "
            "{\"rationale\": \"...\", \"goal\": \"...\", \"priority\": \"LOW|MEDIUM\"}\n"
            "If no action is needed, return 'NONE'."
        )

        response = self.nyx._llm(prompt)
        if response and "{" in response:
            try:
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if not match:
                    return
                data = json.loads(match.group(0))
                self.task_count_hour += 1
                self._log(data["rationale"], data["goal"], "proposed")
                logger.info("Autonomy proposal: %s", data["rationale"])
                self.nyx.process(f"nyx goal \"{data['goal']}\"")
            except Exception as exc:
                self._log("JSON parse error", response, f"failed: {exc}")

    def _log(self, rationale: str, goal: str, status: str):
        """Append an autonomy decision to the audit log."""
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            ts = datetime.datetime.now().isoformat()
            with open(self.log_file, "a") as f:
                f.write(f"[{ts}] [Goal: {goal}] [Why: {rationale}] -> {status}\n")
        except OSError as exc:
            logger.warning("AutonomyEngine: Could not write log: %s", exc)
