import threading
import time
from collections import deque

class TaskPriority:
    HIGH = 10
    MEDIUM = 5
    LOW = 1

class TaskQueue:
    def __init__(self, aging_interval=60):
        self.queue = [] # List of tasks: (priority, timestamp, task_dict)
        self.lock = threading.Lock()
        self.aging_interval = aging_interval # seconds

    def push(self, task):
        with self.lock:
            priority = task.get("priority", TaskPriority.LOW)
            # Use timestamp to maintain FIFO within same priority
            self.queue.append([priority, time.time(), task])
            # Sort by priority descending, then timestamp ascending
            self.queue.sort(key=lambda x: (-x[0], x[1]))

    def pop(self):
        with self.lock:
            if not self.queue:
                return None
            # Return the top task
            return self.queue.pop(0)[2]

    def age_tasks(self):
        """Increase priority of tasks that have been waiting too long."""
        with self.lock:
            now = time.time()
            for entry in self.queue:
                wait_time = now - entry[1]
                if wait_time > self.aging_interval:
                    # Bump priority but cap at HIGH
                    entry[0] = min(entry[0] + 1, TaskPriority.HIGH)
            # Re-sort
            self.queue.sort(key=lambda x: (-x[0], x[1]))

    def get_snapshot(self):
        with self.lock:
            return [
                {
                    "task_id": item[2]["id"],
                    "priority": item[0],
                    "wait_time": time.time() - item[1],
                    "goal": item[2].get("goal", "Unknown")
                }
                for item in self.queue
            ]

    @property
    def size(self):
        with self.lock:
            return len(self.queue)
