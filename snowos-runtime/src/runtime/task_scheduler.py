"""
SnowOS Runtime — TaskScheduler & Temporal Engine
==================================================
Extracted from nyx.py (Stage 18).

Provides a persistent task queue with:
  - Priority levels (HIGH, NORMAL, LOW)
  - Delayed execution via run_at timestamps
  - Recurrence via interval_sec
  - Dependency chains (task B runs only after task A completes)
  - A background thread that ticks every 5 seconds

Task schema:
{
  "id": "uuid8",
  "goal": "setup flask project",
  "cwd": "/path",
  "priority": "HIGH|NORMAL|LOW",
  "status": "pending|running|done|failed|cancelled",
  "run_at": ISO timestamp or null,
  "interval_sec": int or null,
  "depends_on": ["task_id", ...],
  "created_at": ISO timestamp,
  "completed_at": ISO timestamp or null,
}
"""

import os
import json
import uuid
import datetime
import threading
import logging

logger = logging.getLogger("SnowOS.TaskScheduler")

PRIORITY = {"HIGH": 0, "NORMAL": 1, "LOW": 2}


class TaskScheduler:
    """
    Persistent task queue with priority, dependency chains,
    delayed execution, and optional recurrence.
    """

    TICK_INTERVAL = 5  # seconds between scheduler ticks

    def __init__(self, queue_file: str, nyx_agent):
        self.queue_file = queue_file
        self.nyx = nyx_agent
        self.queue: dict[str, dict] = self._load()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="NyxScheduler"
        )

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file) as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("TaskScheduler: Could not load queue (%s) — starting fresh.", exc)
        return {}

    def _save(self):
        with open(self.queue_file, "w") as f:
            json.dump(self.queue, f, indent=2)

    # ── Public task API ───────────────────────────────────────────────────────

    def schedule(
        self,
        goal: str,
        cwd: str,
        priority: str = "NORMAL",
        delay_sec: int = 0,
        interval_sec: int | None = None,
        depends_on: list[str] | None = None,
        goal_id: str | None = None,
    ) -> str:
        """Add a new task to the queue. Returns the task ID."""
        task_id = str(uuid.uuid4())[:8]
        run_at = None
        if delay_sec > 0:
            run_at = (
                datetime.datetime.now() + datetime.timedelta(seconds=delay_sec)
            ).isoformat()

        self.queue[task_id] = {
            "id": task_id,
            "goal": goal,
            "cwd": cwd,
            "priority": priority.upper() if priority.upper() in PRIORITY else "NORMAL",
            "status": "pending",
            "run_at": run_at,
            "interval_sec": interval_sec,
            "depends_on": depends_on or [],
            "created_at": datetime.datetime.now().isoformat(),
            "completed_at": None,
            "goal_id": goal_id,
        }
        self._save()
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task. Returns True if cancelled."""
        if task_id in self.queue and self.queue[task_id]["status"] == "pending":
            self.queue[task_id]["status"] = "cancelled"
            self._save()
            return True
        return False

    def list_tasks(self) -> list[dict]:
        """Return all tasks sorted by priority then creation time."""
        return sorted(
            self.queue.values(),
            key=lambda t: (PRIORITY.get(t["priority"], 1), t["created_at"]),
        )

    # ── Background scheduler ──────────────────────────────────────────────────

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.error("TaskScheduler tick error: %s", exc)
            self._stop_event.wait(self.TICK_INTERVAL)

    def _tick(self):
        """Dispatch ready tasks to the Nyx scheduler engine."""
        ready = [
            t for t in self.queue.values()
            if t["status"] == "pending"
            and self._is_due(t)
            and self._deps_satisfied(t)
        ]
        ready.sort(key=lambda t: PRIORITY.get(t["priority"], 1))

        pool = getattr(self.nyx, "scheduler_engine", None)
        priority_map = {"HIGH": 10, "NORMAL": 5, "LOW": 1}

        for task in ready:
            task["status"] = "running"
            self._save()

            if pool:
                pool.submit(
                    goal=task["goal"],
                    cwd=task["cwd"],
                    priority=priority_map.get(task["priority"], 5),
                    on_complete=lambda _r, tid=task["id"]: self._mark_done(tid),
                )
            else:
                self.nyx.process(task["goal"])
                self._mark_done(task["id"])

    def _mark_done(self, task_id: str):
        if task_id in self.queue:
            task = self.queue[task_id]
            task["status"] = "done"
            task["completed_at"] = datetime.datetime.now().isoformat()

            # Reschedule recurring tasks
            if task.get("interval_sec"):
                self.schedule(
                    goal=task["goal"],
                    cwd=task["cwd"],
                    priority=task["priority"],
                    delay_sec=task["interval_sec"],
                    interval_sec=task["interval_sec"],
                    goal_id=task.get("goal_id"),
                )
            self._save()

    # ── Dependency resolution ─────────────────────────────────────────────────

    def _deps_satisfied(self, task: dict) -> bool:
        for dep_id in task.get("depends_on", []):
            dep = self.queue.get(dep_id)
            if not dep or dep["status"] != "done":
                return False
        return True

    def _is_due(self, task: dict) -> bool:
        if task["run_at"] is None:
            return True
        return datetime.datetime.now() >= datetime.datetime.fromisoformat(task["run_at"])
