import os
import json
import logging

logger = logging.getLogger("SnowOS.VectorMemory")

try:
    import chromadb
    from chromadb.config import Settings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


class _FallbackCollection:
    """Lightweight in-process vector/text memory fallback when chromadb is not installed."""
    def __init__(self, storage_file: str):
        self.storage_file = storage_file
        self.items = []
        self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.items = json.load(f)
            except Exception:
                self.items = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.items, f)
        except (OSError, PermissionError):
            pass

    def clear(self):
        self.items = []
        self._save()

    def add(self, documents, metadatas=None, ids=None):
        metadatas = metadatas or [{}] * len(documents)
        ids = ids or [os.urandom(8).hex() for _ in documents]
        for doc, meta, item_id in zip(documents, metadatas, ids):
            self.items.append({
                "id": str(item_id),
                "document": str(doc),
                "metadata": meta or {}
            })
        self._save()

    def query(self, query_texts, n_results=3):
        res_ids = []
        res_docs = []
        res_metas = []
        res_dists = []
        for q in query_texts:
            q_words = set(str(q).lower().split())
            scored = []
            for item in self.items:
                doc_words = set(item["document"].lower().split())
                overlap = len(q_words & doc_words)
                # distance between 0.0 (identical) and 1.0 (no overlap)
                dist = 1.0 - (overlap / max(1, len(q_words)))
                scored.append((dist, item))
            scored.sort(key=lambda x: x[0])
            top = scored[:n_results]
            res_ids.append([x[1]["id"] for x in top])
            res_docs.append([x[1]["document"] for x in top])
            res_metas.append([x[1]["metadata"] for x in top])
            res_dists.append([x[0] for x in top])
        return {
            "ids": res_ids,
            "documents": res_docs,
            "metadatas": res_metas,
            "distances": res_dists
        }


class VectorMemory:
    def __init__(self, db_path=None):
        default_dir = os.environ.get("SNOWOS_DATA_DIR") or os.path.expanduser("~/.snowos")
        candidate_path = db_path or os.path.join(default_dir, "nyx/vector_db")
        try:
            os.makedirs(candidate_path, exist_ok=True)
            self.db_path = candidate_path
        except (OSError, PermissionError):
            self.db_path = "/tmp/snowos/vector_db"
            os.makedirs(self.db_path, exist_ok=True)

        if _CHROMA_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=self.db_path)
                self.collection = self.client.get_or_create_collection(
                    name="snowos_memory",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.warning("Chromadb init failed, using resilient fallback: %s", e)
                self.client = None
                self.collection = _FallbackCollection(os.path.join(self.db_path, "fallback_memory.json"))
        else:
            self.client = None
            self.collection = _FallbackCollection(os.path.join(self.db_path, "fallback_memory.json"))

    def add_interaction(self, text, metadata=None, interaction_id=None):
        """Adds a UI interaction or system event to the semantic memory."""
        self.collection.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[interaction_id or os.urandom(8).hex()]
        )

    def query(self, query_text, n_results=3):
        """Queries the memory for semantically similar interactions."""
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )

    def clear(self):
        """Clears the entire semantic memory."""
        if _CHROMA_AVAILABLE and self.client:
            try:
                self.client.delete_collection("snowos_memory")
                self.collection = self.client.get_or_create_collection(name="snowos_memory")
                return
            except Exception:
                pass
        fallback_file = os.path.join(self.db_path, "fallback_memory.json")
        if os.path.exists(fallback_file):
            try:
                os.remove(fallback_file)
            except OSError:
                pass
        if hasattr(self.collection, "clear"):
            self.collection.clear()
        else:
            self.collection = _FallbackCollection(fallback_file)
