import sys
import os

# Add nyx to path
sys.path.append(os.path.expanduser("~/snowos"))
sys.path.append(os.path.expanduser("~/snowos/nyx"))

from nyx.interface.ui_memory import UIMemory

def test_semantic_memory():
    print("--- Initializing UIMemory ---")
    mem = UIMemory()
    
    print("--- Recording Interactions ---")
    mem.record_placement("Firefox", 100, 100, 800, 600)
    mem.record_placement("Terminal", 50, 50, 600, 400)
    mem.record_placement("VSCode", 200, 200, 1024, 768)
    
    print("--- Testing Semantic Query ---")
    # Query for something related but not exact
    query = "Where did I put the web browser?"
    results = mem.learn_from_session(query)
    
    print(f"Query: {query}")
    print("Results:")
    for i, doc in enumerate(results['documents'][0]):
        print(f"{i+1}: {doc} (Distance: {results['distances'][0][i]})")

if __name__ == "__main__":
    try:
        test_semantic_memory()
    except Exception as e:
        print(f"Error: {e}")
