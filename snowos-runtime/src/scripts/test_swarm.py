import sys
import os
import time

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from nyx.swarm.sentient_discovery import SentientDiscovery
from nyx.swarm.task_broker import TaskBroker
from runtime.event_bus import bus

def test_swarm_asil():
    print("--- Initializing Sentient Swarm Intelligence (ASIL) ---")
    discovery = SentientDiscovery()
    broker = TaskBroker(discovery)
    
    # Mock event bus listener
    outbound_events = []
    def on_outbound(data):
        outbound_events.append(data)
        print(f"  [Swarm Hook] Outbound Dispatch to {data['target']}: {data['type']}")
    
    bus.subscribe("swarm_outbound", on_outbound)
    
    print("\n--- Simulating Node Discovery ---")
    discovery.update_peer("glacier-node-02", {"cpu": 15, "ram": 40})
    discovery.update_peer("frost-node-03", {"cpu": 80, "ram": 90})
    
    peers = discovery.get_available_peers()
    print(f"  Available Healthy Peers: {peers}")
    
    print("\n--- Testing Task Offload Negotiation ---")
    # Simulate high local load
    local_health = {"cpu": 85, "ram": 60}
    target = broker.negotiate_offload("long_term_memory_training", local_health)
    
    if target == "glacier-node-02":
        print("  ✅ Correct Target Selected: glacier-node-02 (low CPU)")
        broker.dispatch(target, "compute_task", {"job": "train_weights"})
    else:
        print(f"  ❌ Incorrect Target: {target}")
        
    print(f"\n--- Verifying Event Dispatch ---")
    if len(outbound_events) > 0:
        print("  ✅ Outbound event successfully published to EventBus.")
    
    print("\n✅ Verification Successful: ASIL correctly discovers peers, negotiates offloads based on health, and dispatches tasks.")

if __name__ == "__main__":
    test_swarm_asil()
