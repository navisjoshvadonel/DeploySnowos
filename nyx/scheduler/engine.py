import threading
import time
import concurrent.futures
import uuid
import os
from .queue import TaskQueue, TaskPriority
from .monitor import ResourceMonitor
from .policy import ResourcePolicy
from .cgroups import CgroupEnforcer

class SchedulerEngine:
    def __init__(self, storage=None, max_workers=4):
        self.queue = TaskQueue()
        self.monitor = ResourceMonitor()
        self.storage = storage # Observability DB
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, 
            thread_name_prefix="RAEE-Worker"
        )
        self.active_workers: dict[str, dict] = {} # task_id -> info
        self.user_task_counts: dict[str, int] = {} # user_id -> count
        self.max_per_user = 2 # Default quota
        self.running = False
        self._lock = threading.Lock()

    def start(self):
        self.running = True
        threading.Thread(target=self._scheduler_loop, daemon=True).start()
        threading.Thread(target=self._aging_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.executor.shutdown(wait=False)

    def submit(self, task):
        task_id = task.get("id", str(uuid.uuid4())[:8])
        task["id"] = task_id
        task["enqueue_time"] = time.time()
        
        user_id = task.get("user_id", "anonymous")
        role = task.get("role", "viewer")
        
        self.queue.push(task)
        
        # Log scheduling event
        if self.storage:
            self._record_event(task, "PENDING")
            
        return task_id

    def _scheduler_loop(self):
        while self.running:
            # Check for backpressure
            if self.monitor.is_overloaded():
                # If overloaded, only process HIGH priority if possible, else sleep
                time.sleep(1)
                continue

            with self._lock:
                active_count = len(self.active_workers)
            
            if active_count < self.max_workers:
                # Fair task selection: skip users at quota
                task = self._pop_fair_task()
                if task:
                    self._dispatch(task)
            
            time.sleep(0.5)

    def _pop_fair_task(self):
        """Pops a task while respecting per-user quotas and fairness."""
        with self.queue.lock:
            for i in range(len(self.queue.queue)):
                task = self.queue.queue[i][2]
                user_id = task.get("user_id", "anonymous")
                
                with self._lock:
                    user_count = self.user_task_counts.get(user_id, 0)
                
                if user_count < self.max_per_user:
                    # Remove from queue and return
                    return self.queue.queue.pop(i)[2]
            
            # If all users are at quota but we have capacity, maybe take the oldest?
            # Or just wait for a slot to open up.
            return None

    def _aging_loop(self):
        while self.running:
            self.queue.age_tasks()
            time.sleep(30)

    def _dispatch(self, task):
        task_id = task["id"]
        user_id = task.get("user_id", "anonymous")
        priority = task.get("priority", TaskPriority.LOW)
        
        # MODERN OS FEATURE: Predictive Resource Sizing
        # Predict limits based on task description/type instead of static levels
        limits = self._predict_cost(task)
        
        with self._lock:
            self.active_workers[task_id] = {
                "task": task,
                "start_time": time.time(),
                "limits": limits
            }
            self.user_task_counts[user_id] = self.user_task_counts.get(user_id, 0) + 1

        # Run in worker pool
        self.executor.submit(self._worker_wrapper, task, limits)

    def _predict_cost(self, task):
        """
        PREDICTIVE SCHEDULING:
        In a fully evolved OS, this would use a local model to predict 
        the footprint based on task['description'].
        For now, we use an 'Intelligent Heuristic' that scales with user history.
        """
        priority = task.get("priority", TaskPriority.LOW)
        base_limits = ResourcePolicy.get_limits(priority).copy()
        
        # Heuristic: Increase limits if the task involves 'heavy' keywords
        desc = str(task.get("description", "")).lower()
        if any(kw in desc for kw in ["compile", "build", "render", "inference"]):
            base_limits["cpu_quota"] = min(80, base_limits.get("cpu_quota", 20) * 2)
            base_limits["memory_limit"] = "1G" if "1G" not in base_limits.get("memory_limit", "") else "2G"
            
        return base_limits

    def _worker_wrapper(self, task, limits):
        task_id = task["id"]
        task["start_time"] = time.time()
        wait_time = task["start_time"] - task["enqueue_time"]
        
        if self.storage:
            self._update_event(task_id, start_time=task["start_time"], wait_time=wait_time, status="RUNNING")

        try:
            # The actual task execution logic
            # This will be hooked into NyxAI.run_plan logic
            handler = task.get("handler")
            if handler:
                # Wrap with cgroups if available
                # Note: This is an abstraction, the handler itself must use this wrapper
                # or we wrap the entire sandbox process.
                handler(task, limits)
                
            status = "SUCCESS"
        except Exception as e:
            status = f"FAILED: {str(e)}"
        finally:
            end_time = time.time()
            exec_time = end_time - task["start_time"]
            user_id = task.get("user_id", "anonymous")
            
            with self._lock:
                if task_id in self.active_workers:
                    del self.active_workers[task_id]
                if user_id in self.user_task_counts:
                    self.user_task_counts[user_id] = max(0, self.user_task_counts[user_id] - 1)

            if self.storage:
                self._update_event(task_id, end_time=end_time, execution_time=exec_time, status=status)

    def _record_event(self, task, status):
        if self.storage:
            self.storage.save_scheduling_event(
                task_id=task["id"],
                plan_id=task.get("plan_id"),
                user_id=task.get("user_id"),
                role=task.get("role"),
                priority=task.get("priority", TaskPriority.LOW),
                enqueue_time=task["enqueue_time"],
                status=status
            )

    def _update_event(self, task_id, **kwargs):
        if self.storage:
            self.storage.update_scheduling_event(task_id, **kwargs)

    def get_status(self):
        return {
            "load": self.monitor.get_system_load(),
            "queue_size": self.queue.size,
            "active_workers": len(self.active_workers),
            "pending_tasks": self.queue.get_snapshot()
        }
