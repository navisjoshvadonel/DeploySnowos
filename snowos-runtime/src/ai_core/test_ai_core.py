import sys
import os
import time
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from memory_engine.memory_store import MemoryStore
from decision_engine.decider import DecisionEngine
from learning_engine.feedback_loop import FeedbackLoop
from federated_node.swarm_sync import SwarmSync

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def run_scenario():
    print("\n--- SNOWOS AI CORE EVOLUTION TEST ---")
    
    # Initialize components
    memory = MemoryStore()
    decider = DecisionEngine(memory)
    learner = FeedbackLoop(memory)
    federated = SwarmSync()
    
    print("\n[Phase 1: First Encounter (Low Confidence)]")
    # AI wants to throttle updater during a game
    decision_info = decider.evaluate_action("throttle", "system.updater")
    
    if decision_info["status"] == "REQUIRE_USER_APPROVAL":
        print(f"-> AI halted execution. Prompting user in SnowControl...")
        # Simulate user clicking "Allow"
        time.sleep(1)
        print("-> User clicked 'ALLOW'. Execution proceeded.")
        # Simulate outcome being positive (frame rate improved, user didn't revert)
        learner.process_outcome(decision_info["decision_id"], "success")
        
    print("\n[Phase 2: Second Encounter (Learning Applied)]")
    time.sleep(1)
    # AI encounters the exact same scenario later
    decision_info_2 = decider.evaluate_action("throttle", "system.updater")
    
    if decision_info_2["status"] == "APPROVED":
        print("-> AI executed action autonomously based on historical learning!")
        
    print("\n[Phase 3: Federated Swarm Sync]")
    # Share the successful learned weight with the global swarm
    time.sleep(1)
    federated.generate_anonymized_payload(memory)
    
    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    run_scenario()
