import queue
import threading
import time
import logging

class AIScheduler:
    """Staggers expensive AI tasks to prevent system jitter."""
    
    def __init__(self, resource_manager):
        self.rm = resource_manager
        self.task_queue = queue.PriorityQueue()
        self.logger = logging.getLogger("SnowOS.AIScheduler")
        self.active = True
        
        self.worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.worker_thread.start()

    def defer(self, task_func, priority=10, args=(), callback=None):
        """Add a task to the deferred queue."""
        # Lower number = higher priority
        self.task_queue.put((priority, time.time(), task_func, args, callback))
        self.logger.debug(f"Scheduler: Deferred task {task_func.__name__} (priority: {priority})")

    def _process_loop(self):
        """Worker loop that handles tasks with appropriate spacing."""
        while self.active:
            try:
                # 1. Get task
                priority, _, func, args, callback = self.task_queue.get(timeout=1.0)
                
                # 2. Check throttling from resource manager
                # Use current system mode for throttling (stubbed as 'balanced' for test)
                throttle = 0.05 # Base delay to prevent micro-bursts
                time.sleep(throttle)
                
                # 3. Execute
                start = time.time()
                result = func(*args)
                duration = time.time() - start
                
                if callback:
                    callback(result)
                
                self.logger.debug(f"Scheduler: Finished {func.__name__} in {int(duration*1000)}ms")
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Scheduler: Task failed: {e}")

    def stop(self):
        self.active = False
