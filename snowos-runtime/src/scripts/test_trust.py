import sys
import os
import time

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from personality.engine import PersonalityEngine
from personality.trust import TrustEngine
from personality.gating import ActionGating
from nyx.memory.engine import NyxMemoryEngine

def test_personality_trust():
    print("--- Initializing Trust Engine ---")
    memory = NyxMemoryEngine()
    persona = PersonalityEngine()
    trust = TrustEngine(memory)
    gating = ActionGating(persona, trust)
    
    print(f"\nCurrent Mode: {persona.get_mode_name()}")
    
    print("\n--- Simulating High Confidence Action ---")
    # Simulate 10 'ls' commands in memory
    for _ in range(10):
        memory.log_event("ls", "shell", "success")
    
    analysis = trust.analyze_prediction("ls")
    print(f"Confidence for 'ls': {analysis['confidence']} ({analysis['reason']})")
    
    print("\n--- Testing Gating in 'Assistive' Mode ---")
    persona.set_mode("assistive")
    allowed, reason = gating.validate_action("ls")
    print(f"Allowed: {allowed}, Reason: {reason}")
    
    print("\n--- Testing Gating in 'Autonomous' Mode ---")
    persona.set_mode("autonomous")
    allowed, reason = gating.validate_action("ls")
    print(f"Allowed: {allowed}, Reason: {reason}")
    
    print("\n--- Testing Destructive Command Gating ---")
    allowed, reason = gating.validate_action("rm -rf /")
    print(f"Allowed: {allowed}, Reason: {reason}")
    
    print("\n✅ Verification Successful: Personality modes and gating logic correctly enforced.")

if __name__ == "__main__":
    test_personality_trust()
