import sys
import os
import time

# Add memory module to path
sys.path.append(os.path.expanduser("~/snowos/nyx"))
from memory.engine import NyxMemoryEngine

def test_memory():
    engine = NyxMemoryEngine()
    
    print("--- Simulating Activity ---")
    actions = [
        ("ls", "shell", "success"),
        ("cd ..", "shell", "success"),
        ("ls", "shell", "success"),
        ("cd ..", "shell", "success"),
        ("ls", "shell", "success"),
        ("python3 --version", "shell", "success")
    ]
    
    for cmd, act, status in actions:
        print(f"Logging: {cmd}")
        engine.log_event(cmd, act, status)
        
    print("\n--- Predictions ---")
    suggestions = engine.get_suggestions()
    print(f"Suggestions: {suggestions}")
    
    frequent = engine.get_frequent_apps()
    print(f"Frequent Apps: {frequent}")
    
    next_action = engine.predict_next_action()
    print(f"Predicted Next Action: {next_action}")

if __name__ == "__main__":
    test_memory()
