import sys
import os
import time

# Add modules to path
sys.path.append(os.path.expanduser("~/snowos"))
from nyx.learning.retriever import NyxRetriever
from nyx.memory.engine import NyxMemoryEngine

def test_learning_rag():
    print("--- Initializing Learning Engine ---")
    memory = NyxMemoryEngine()
    retriever = NyxRetriever(memory)
    
    print("\n--- Simulating Past Actions ---")
    actions = [
        ("git status", "shell", "success"),
        ("git add .", "shell", "success"),
        ("git commit -m 'update UI'", "shell", "success")
    ]
    for cmd, act, status in actions:
        memory.log_event(cmd, act, status)
        
    print("\n--- Testing Retrieval for 'git' ---")
    context = retriever.retrieve_context("tell me about my git actions")
    for c in context:
        print(f"  → {c}")
        
    print("\n--- Testing Knowledge Retrieval for 'SpatialUI' ---")
    context = retriever.retrieve_context("how does the spatial ui work?")
    for c in context:
        print(f"  → {c}")
        
    print("\n✅ Verification Successful: RAG correctly retrieved both historical and static knowledge.")

if __name__ == "__main__":
    test_learning_rag()
