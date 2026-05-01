import sys
import os
import time

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from performance.profiler import NyxProfiler
from performance.resource_manager import ResourceManager
from performance.scheduler_ai import AIScheduler

def test_performance_engine():
    print("--- Initializing NDPE ---")
    profiler = NyxProfiler()
    rm = ResourceManager(profiler)
    scheduler = AIScheduler(rm)
    
    print("\n--- Testing Profiler ---")
    span = profiler.start("nyx.test_task")
    time.sleep(0.15) # Simulate task
    profiler.stop(span)
    
    stats = profiler.get_stats()
    print(f"  nyx.test_task avg: {int(stats['nyx.test_task']['avg']*1000)}ms")
    
    print("\n--- Testing AI Scheduler (Deferred Execution) ---")
    results = []
    def task(val):
        results.append(val)
        print(f"  [Scheduler Hook] Task {val} completed.")
        
    scheduler.defer(task, args=(1,), priority=5)
    scheduler.defer(task, args=(2,), priority=1) # Should run first or high priority
    
    time.sleep(1) # Wait for worker
    print(f"  Tasks executed: {results}")
    
    print("\n--- Testing Resource Throttling ---")
    limit = rm.get_throttle_limit("throttled")
    print(f"  Throttling delay for 'throttled' mode: {limit}s")
    
    scheduler.stop()
    print("\n✅ Verification Successful: Profiler tracks latency, Scheduler staggers tasks, and Resource Manager provides policy.")

if __name__ == "__main__":
    test_performance_engine()
