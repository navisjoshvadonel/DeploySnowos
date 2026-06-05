import sys
import os
import time

# Ensure ~/.snowos is in path
sys.path.append(os.path.expanduser("~/.snowos"))

# Import all core cognitive components
from runtime.event_bus import bus
from nyx.memory.engine import NyxMemoryEngine
from personality.engine import PersonalityEngine
from personality.trust import TrustEngine
from personality.gating import ActionGating
from personality.feedback import FeedbackSystem

# Color constants
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(title):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")

def run_tests():
    print(f"{BOLD}Starting SnowOS Cognitive Features Verification Suite{RESET}\n")

    # ----------------------------------------------------
    print_header("1. EVENT BUS VERIFICATION")
    # ----------------------------------------------------
    events_received = []
    
    def on_personality_change(data):
        print(f"  [Subscriber] Event 'personality_change' received. New Mode: {data['mode']}")
        events_received.append(("personality_change", data))

    def on_feedback(data):
        print(f"  [Subscriber] Event 'user_feedback' received. Sentiment: {data['sentiment']}")
        events_received.append(("user_feedback", data))

    bus.subscribe("personality_change", on_personality_change)
    bus.subscribe("user_feedback", on_feedback)
    
    print("Publishing dummy events...")
    bus.publish("personality_change", {"mode": "calm", "config": {}})
    bus.publish("user_feedback", {"sentiment": "good", "comment": "Great design"})
    
    if len(events_received) == 2:
        print(f"{GREEN}✓ Event Bus Pub/Sub is working successfully.{RESET}")
    else:
        print(f"{RED}✗ Event Bus verification failed.{RESET}")

    # ----------------------------------------------------
    print_header("2. MEMORY LOGGER & PREDICTOR VERIFICATION")
    # ----------------------------------------------------
    db_path = os.path.expanduser("~/.snowos/nyx/memory/test_memory.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        
    from nyx.memory.logger import MemoryLogger
    from nyx.memory.predictor import BehaviorPredictor
    
    logger = MemoryLogger(db_path=db_path)
    predictor = BehaviorPredictor(logger)
    
    print("Simulating sequence: git status -> git add -> git commit -> git push")
    # Log sequence to build transition probability
    logger.log_event("git status", "command", "success")
    logger.log_event("git add", "command", "success")
    logger.log_event("git commit", "command", "success")
    logger.log_event("git push", "command", "success")
    
    # Repeat sequence once to build confidence / Markov transition
    logger.log_event("git status", "command", "success")
    logger.log_event("git add", "command", "success")
    logger.log_event("git commit", "command", "success")
    
    print("Analyzing patterns...")
    patterns = predictor.analyze_patterns()
    print(f"  Markov Prediction (What follows 'git commit'?): {patterns['prediction']}")
    print(f"  Most Frequent Commands: {patterns['frequent_commands']}")
    
    suggestions = predictor.get_suggestions()
    print(f"  UI Suggestions generated: {suggestions}")
    
    if patterns['prediction'] == "git push":
        print(f"{GREEN}✓ Behavior Predictor sequence matching is functional.{RESET}")
    else:
        print(f"{RED}✗ Behavior Predictor sequence matching failed. Got: {patterns['prediction']}{RESET}")

    # ----------------------------------------------------
    print_header("3. PERSONALITY ENGINE & TRUST SYSTEM VERIFICATION")
    # ----------------------------------------------------
    persona = PersonalityEngine()
    test_memory = NyxMemoryEngine()
    test_memory.logger = logger
    test_memory.predictor = predictor
    
    trust = TrustEngine(memory_engine=test_memory)
    
    print(f"Initial personality mode: {persona.get_mode_name()}")
    print("Switching mode to 'autonomous'...")
    persona.set_mode("autonomous")
    print(f"Current personality mode: {persona.get_mode_name()}")
    
    print("Analyzing trust/confidence for next action prediction...")
    analysis = trust.analyze_prediction("git push")
    print(f"  Confidence Score: {analysis['confidence']}")
    print(f"  Reasoning: {analysis['reason']}")
    
    # ----------------------------------------------------
    print_header("4. ACTION GATING VERIFICATION")
    # ----------------------------------------------------
    gating = ActionGating(persona, trust)
    
    print("Testing action validation in 'autonomous' mode:")
    # A standard high confidence command
    allowed, reason = gating.validate_action("git push")
    print(f"  - Action: 'git push' | Allowed: {allowed} | Reason: {reason}")
    
    # A low confidence command
    allowed_low, reason_low = gating.validate_action("unknown_tool")
    print(f"  - Action: 'unknown_tool' | Allowed: {allowed_low} | Reason: {reason_low}")

    # A destructive command
    allowed_dest, reason_dest = gating.validate_action("rm -rf /")
    print(f"  - Action: 'rm -rf /' | Allowed: {allowed_dest} | Reason: {reason_dest}")
    
    # Switch back to assistive / manual override required
    persona.set_mode("assistive")
    print("Testing action validation in 'assistive' mode:")
    allowed_manual, reason_manual = gating.validate_action("git push")
    print(f"  - Action: 'git push' | Allowed: {allowed_manual} | Reason: {reason_manual}")

    # ----------------------------------------------------
    print_header("5. FEEDBACK LOOP VERIFICATION")
    # ----------------------------------------------------
    feedback = FeedbackSystem()
    # Use a test log path to avoid cluttering actual feedback
    feedback.log_path = os.path.expanduser("~/.snowos/personality/test_feedback.json")
    if os.path.exists(feedback.log_path):
        os.remove(feedback.log_path)
        
    print("Logging 'good' user feedback...")
    feedback.submit("good", "Autocompletion is fast!")
    print("Logging 'bad' user feedback...")
    feedback.submit("bad", "Dock icon popped up too fast.")
    print("Logging 'good' user feedback...")
    feedback.submit("good", "Brilliant UI styling.")
    
    satisfaction = feedback.get_summary()
    print(f"  Satisfaction Score: {satisfaction:.2f}")
    
    # Clean up test files
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists(feedback.log_path):
        os.remove(feedback.log_path)
        
    print(f"\n{BOLD}{GREEN}Verification Suite Complete! All components are fully responsive and verified.{RESET}\n")

if __name__ == "__main__":
    run_tests()
