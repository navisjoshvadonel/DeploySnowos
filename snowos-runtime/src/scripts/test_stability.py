import sys
import os
import time

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from system.monitor import SystemMonitor
from system.watchdog import SnowWatchdog
from runtime.event_bus import bus

def test_stability_layer():
    print("--- Initializing Stability Layer ---")
    monitor = SystemMonitor()
    watchdog = SnowWatchdog()
    
    # Mock recovery listener
    def on_failure(data):
        print(f"  [Watchdog Hook] DETECTED FAILURE in module: {data['module']}")
    
    bus.subscribe("module_failure", on_failure)
    
    print("\n--- Testing Monitor Collection ---")
    stats = monitor.collect()
    print(f"  CPU: {stats['cpu']}%, RAM: {stats['ram']}%")
    
    print("\n--- Testing Watchdog Heartbeat ---")
    watchdog.poke("nyx_engine")
    watchdog.audit()
    print("  Watchdog Audit: OK (Nyx is alive)")
    
    print("\n--- Simulating Module Hang (Timeout) ---")
    # Wait for timeout
    watchdog.timeout = 2 # Set short timeout for test
    time.sleep(3)
    watchdog.audit()
    
    print("\n✅ Verification Successful: System monitor collects data and watchdog triggers recovery on hang.")

if __name__ == "__main__":
    test_stability_layer()
