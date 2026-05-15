import os
import json
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class NyxRetriever:
    """Retrieval-Augmented Generation (RAG) engine for SnowOS."""
    
    def __init__(self, memory_engine):
        self.memory = memory_engine
        self.logger = logging.getLogger("SnowOS.Retriever")
        self.kb_path = os.path.expanduser("~/.snowos/nyx/learning/knowledge_base/system_knowledge.json")
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self._load_kb()

    def _load_kb(self):
        """Index the static knowledge base."""
        try:
            with open(self.kb_path, 'r') as f:
                self.kb = json.load(f)
            
            self.base_corpus = []
            # Index modules
            for name, desc in self.kb.get("modules", {}).items():
                self.base_corpus.append(f"Module {name}: {desc}")
                
            # Index commands
            for cmd, ctx in self.kb.get("command_context", {}).items():
                self.base_corpus.append(f"Command '{cmd}': {ctx}")
        except Exception as e:
            self.logger.error(f"Failed to load KB: {e}")
            self.base_corpus = []

    def retrieve_context(self, query, top_k=3):
        """Find the most relevant past actions and knowledge for a given input."""
        try:
            # 1. Build dynamic corpus (KB + Recent History)
            history = self.memory.logger.get_recent_history(limit=30)
            dynamic_corpus = list(self.base_corpus)
            
            for h in history:
                dynamic_corpus.append(f"Past Action: {h[1]} (Result: {h[3]})")
            
            if not dynamic_corpus:
                return []

            # 2. Vectorize and Search
            tfidf_matrix = self.vectorizer.fit_transform(dynamic_corpus)
            query_vec = self.vectorizer.transform([query])
            
            # 3. Calculate Similarity
            similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
            indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in indices:
                if similarities[idx] > 0.05: # Low threshold for relevance
                    results.append(dynamic_corpus[idx])
            
            return results
        except Exception as e:
            self.logger.error(f"Retrieval error: {e}")
            return []

    def get_enriched_prompt(self, query):
        """Wraps a query with retrieved context for the LLM."""
        context = self.retrieve_context(query)
        if not context:
            return query
            
        context_str = "\n".join([f"- {c}" for c in context])
        enriched = (
            "SYSTEM CONTEXT (NYX MEMORY):\n"
            f"{context_str}\n\n"
            "USER INPUT:\n"
            f"{query}"
        )
        return enriched
