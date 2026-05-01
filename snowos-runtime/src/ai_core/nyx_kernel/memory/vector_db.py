import chromadb
from chromadb.config import Settings
import os

class VectorMemory:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.expanduser("~/snowos/nyx/vector_db")
        os.makedirs(self.db_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(
            name="snowos_memory",
            metadata={"hnsw:space": "cosine"}
        )

    def add_interaction(self, text, metadata=None, interaction_id=None):
        """Adds a UI interaction or system event to the semantic memory."""
        self.collection.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[interaction_id or os.urandom(8).hex()]
        )

    def query(self, query_text, n_results=3):
        """Queries the memory for semantically similar interactions."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results

    def clear(self):
        """Clears the entire semantic memory."""
        self.client.delete_collection("snowos_memory")
        self.collection = self.client.get_or_create_collection(name="snowos_memory")
