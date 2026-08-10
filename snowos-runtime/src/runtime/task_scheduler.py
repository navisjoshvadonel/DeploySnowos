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
from pathlib import Path

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
        self._lock = threading.RLock()
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
        queue_path = Path(self.queue_file)
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = queue_path.with_suffix(queue_path.suffix + ".tmp")
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(self.queue, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, queue_path)

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

        with self._lock:
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
        with self._lock:
            if task_id in self.queue and self.queue[task_id]["status"] == "pending":
                self.queue[task_id]["status"] = "cancelled"
                self._save()
                return True
        return False

    def list_tasks(self) -> list[dict]:
        """Return all tasks sorted by priority then creation time."""
        with self._lock:
            return sorted(
                self.queue.values(),
                key=lambda t: (PRIORITY.get(t["priority"], 1), t["created_at"]),
            )

    # ── Background scheduler ──────────────────────────────────────────────────

    def start(self):
        if not self._thread.is_alive():
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
        with self._lock:
            ready = [
                t.copy() for t in self.queue.values()
                if t["status"] == "pending"
                and self._is_due(t)
                and self._deps_satisfied(t)
            ]
        ready.sort(key=lambda t: PRIORITY.get(t["priority"], 1))

        pool = getattr(self.nyx, "scheduler_engine", None)
        priority_map = {"HIGH": 10, "NORMAL": 5, "LOW": 1}
        deferred_priority_map = {"HIGH": 1, "NORMAL": 5, "LOW": 10}

        for task in ready:
            with self._lock:
                if self.queue.get(task["id"], {}).get("status") != "pending":
                    continue
                self.queue[task["id"]]["status"] = "running"
                self._save()

            if pool and hasattr(pool, "defer"):
                pool.defer(
                    self._execute,
                    priority=deferred_priority_map.get(task["priority"], 5),
                    args=(task,),
                )
            elif pool and hasattr(pool, "submit"):
                pool.submit(
                    {
                        "id": task["id"],
                        "description": task["goal"],
                        "priority": priority_map.get(task["priority"], 5),
                        "handler": lambda _task, _limits, queued_task=task: self._execute(queued_task),
                    }
                )
            else:
                self._execute(task)

    def _execute(self, task: dict):
        try:
            self.nyx.process(task["goal"])
        except Exception as exc:
            logger.exception("Scheduled task %s failed", task["id"])
            self._mark_failed(task["id"], str(exc))
            raise
        self._mark_done(task["id"])

    def _mark_done(self, task_id: str):
        with self._lock:
            if task_id not in self.queue:
                return
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

    def _mark_failed(self, task_id: str, error: str):
        with self._lock:
            if task_id in self.queue:
                task = self.queue[task_id]
                task["status"] = "failed"
                task["completed_at"] = datetime.datetime.now().isoformat()
                task["error"] = error
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
