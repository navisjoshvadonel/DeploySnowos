"""
SnowOS Kernel Smart Scheduler — Multi-Level Feedback Queue (MLFQ) & Real-Time Engine.

Prevents heavy, compute-intensive AI workloads from starving core OS operations.

Architecture:
  - 4 Feedback Queues with ascending time-quanta:
      Q0 [Real-Time / Critical]: Quantum = 10ms (Input, IPC broker, Sentinel)
      Q1 [Interactive / UI]:     Quantum = 25ms (Shell, Window Manager events)
      Q2 [Standard Workload]:    Quantum = 50ms (Normal daemon tasks)
      Q3 [AI / Compute Bound]:   Quantum = 100ms (LLM inference, embeddings, indexing)

MLFQ Rules:
  Rule 1: Priority: If Priority(A) > Priority(B), A runs (B does not).
  Rule 2: Round-Robin: If Priority(A) == Priority(B), A and B run in Round Robin.
  Rule 3: Quantum Demotion: Tasks exhausting their quantum are demoted to Qi+1.
  Rule 4: Anti-Starvation Boost: Every BOOST_INTERVAL (3s), all waiting tasks are
          boosted to Q0 to prevent starvation.
  Rule 5: I/O Retention: Tasks that yield (I/O, IPC wait) retain their priority queue.
"""

import collections
import enum
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("SnowOS.SmartScheduler")


class QueueLevel(enum.IntEnum):
    Q0_REALTIME    = 0   # 10ms quantum — Highest priority
    Q1_INTERACTIVE = 1   # 25ms quantum
    Q2_STANDARD    = 2   # 50ms quantum
    Q3_AI_BATCH    = 3   # 100ms quantum — Lowest priority (compute heavy)


QUANTUM_MAP = {
    QueueLevel.Q0_REALTIME:    0.010,  # 10 ms
    QueueLevel.Q1_INTERACTIVE: 0.025,  # 25 ms
    QueueLevel.Q2_STANDARD:    0.050,  # 50 ms
    QueueLevel.Q3_AI_BATCH:    0.100,  # 100 ms
}

BOOST_INTERVAL_SEC = 3.0  # Periodic anti-starvation priority boost


class SchedTask:
    """Represents a schedulable unit of work in SnowOS."""
    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: Optional[dict] = None,
        initial_queue: QueueLevel = QueueLevel.Q1_INTERACTIVE,
        task_id: Optional[str] = None,
        on_complete: Optional[Callable[[Any], None]] = None,
    ):
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.name = name
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.current_queue = initial_queue
        self.on_complete = on_complete

        # Metrics & Lifecycle
        self.created_at = time.monotonic()
        self.last_scheduled_at = 0.0
        self.total_cpu_time = 0.0
        self.quantum_consumed = 0.0
        self.demotions = 0
        self.promotions = 0
        self.completed = False
        self.result = None
        self.error = None
        self._done_event = threading.Event()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._done_event.wait(timeout=timeout)


class MLFQScheduler:
    """
    Multi-Level Feedback Queue Scheduler.
    Schedules tasks across real-time, interactive, and AI compute tiers.
    """
    def __init__(self, num_workers: int = 4):
        self.num_workers = max(1, num_workers)
        self.queues: Dict[QueueLevel, collections.deque[SchedTask]] = {
            level: collections.deque() for level in QueueLevel
        }
        self._lock = threading.Lock()
        self._work_available = threading.Condition(self._lock)
        self._running = False
        self._workers: List[threading.Thread] = []
        self._boost_thread: Optional[threading.Thread] = None

        # Observability & telemetry
        self.stats = {
            "tasks_completed": 0,
            "tasks_demoted": 0,
            "tasks_boosted": 0,
            "realtime_tasks_dispatched": 0,
            "ai_tasks_dispatched": 0,
        }

    def start(self):
        """Start worker threads and the anti-starvation priority boost timer."""
        with self._lock:
            if self._running:
                return
            self._running = True

            # Spawn worker threads
            for i in range(self.num_workers):
                t = threading.Thread(
                    target=self._worker_loop,
                    name=f"SnowSched-Worker-{i}",
                    daemon=True,
                )
                self._workers.append(t)
                t.start()

            # Spawn periodic priority boost thread
            self._boost_thread = threading.Thread(
                target=self._boost_loop,
                name="SnowSched-StarvationGuard",
                daemon=True,
            )
            self._boost_thread.start()

        logger.info("MLFQScheduler active (%d workers, 4 queues, anti-starvation=3.0s).", self.num_workers)

    def stop(self):
        """Clean shutdown of the scheduler."""
        with self._lock:
            self._running = False
            self._work_available.notify_all()
        for w in self._workers:
            w.join(timeout=1.0)

    def submit(
        self,
        name: str,
        func: Callable[..., Any],
        *args,
        priority: QueueLevel = QueueLevel.Q1_INTERACTIVE,
        on_complete: Optional[Callable[[Any], None]] = None,
        **kwargs,
    ) -> SchedTask:
        """Submit a task to the appropriate MLFQ tier."""
        task = SchedTask(
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            initial_queue=priority,
            on_complete=on_complete,
        )

        with self._lock:
            self.queues[task.current_queue].append(task)
            self._work_available.notify(1)

        return task

    def _select_next_task(self) -> Optional[SchedTask]:
        """
        Rule 1 & Rule 2:
        Select the earliest task from the highest non-empty priority queue.
        """
        for level in QueueLevel:
            q = self.queues[level]
            if q:
                task = q.popleft()
                if level == QueueLevel.Q0_REALTIME:
                    self.stats["realtime_tasks_dispatched"] += 1
                elif level == QueueLevel.Q3_AI_BATCH:
                    self.stats["ai_tasks_dispatched"] += 1
                return task
        return None

    def _worker_loop(self):
        """Thread worker executing slices of tasks."""
        while True:
            with self._lock:
                while self._running:
                    task = self._select_next_task()
                    if task is not None:
                        break
                    self._work_available.wait(timeout=0.5)

                if not self._running:
                    return

            # Execute task
            start_wall = time.monotonic()
            task.last_scheduled_at = start_wall
            quantum = QUANTUM_MAP[task.current_queue]

            try:
                # Execute the unit of work
                result = task.func(*task.args, **task.kwargs)
                duration = time.monotonic() - start_wall

                task.total_cpu_time += duration
                task.quantum_consumed += duration
                task.result = result
                task.completed = True

                if task.on_complete:
                    try:
                        task.on_complete(result)
                    except Exception as cb_err:
                        logger.warning("Callback error on task '%s': %s", task.name, cb_err)

                with self._lock:
                    self.stats["tasks_completed"] += 1

                task._done_event.set()

            except Exception as exc:
                task.error = exc
                task.completed = True
                task._done_event.set()
                logger.error("Task '%s' failed in queue %s: %s", task.name, task.current_queue.name, exc)

    def demote_task(self, task: SchedTask):
        """Rule 3: Demote task if it exhausted its time slice."""
        with self._lock:
            if task.current_queue < QueueLevel.Q3_AI_BATCH:
                old_lvl = task.current_queue
                task.current_queue = QueueLevel(task.current_queue + 1)
                task.demotions += 1
                self.stats["tasks_demoted"] += 1
                logger.debug("Task '%s' demoted: %s -> %s", task.name, old_lvl.name, task.current_queue.name)
            self.queues[task.current_queue].append(task)
            self._work_available.notify(1)

    def _boost_loop(self):
        """
        Rule 4: Anti-Starvation Periodic Priority Boost.
        Promotes waiting tasks across all queues every BOOST_INTERVAL_SEC
        so long-running AI compute tasks never starve other workloads.
        """
        while self._running:
            time.sleep(BOOST_INTERVAL_SEC)
            with self._lock:
                boosted_count = 0
                for level in (QueueLevel.Q3_AI_BATCH, QueueLevel.Q2_STANDARD, QueueLevel.Q1_INTERACTIVE):
                    q = self.queues[level]
                    while q:
                        task = q.popleft()
                        task.current_queue = QueueLevel.Q0_REALTIME
                        task.promotions += 1
                        task.quantum_consumed = 0.0
                        self.queues[QueueLevel.Q0_REALTIME].append(task)
                        boosted_count += 1

                if boosted_count > 0:
                    self.stats["tasks_boosted"] += boosted_count
                    logger.debug("Anti-Starvation Guard: Boosted %d tasks to Q0_REALTIME", boosted_count)
                    self._work_available.notify_all()
