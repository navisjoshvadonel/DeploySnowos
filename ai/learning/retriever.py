import os
import json
import logging
import math
import re

logger = logging.getLogger("SnowOS.Retriever")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


class _PurePythonTfidf:
    """Lightweight pure-python TF-IDF ranker fallback when sklearn is not installed."""
    STOP_WORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
        "to", "was", "were", "will", "with", "me", "tell", "how", "what",
        "about", "my", "does", "work"
    }

    def __init__(self):
        self.corpus = []
        self.doc_tokens = []
        self.idf = {}

    def _tokenize(self, text: str):
        words = re.findall(r"\w+", text.lower())
        return [w for w in words if w not in self.STOP_WORDS]

    def fit(self, corpus):
        self.corpus = corpus
        self.doc_tokens = [self._tokenize(doc) for doc in corpus]
        n_docs = len(corpus)
        df = {}
        for tokens in self.doc_tokens:
            for w in set(tokens):
                df[w] = df.get(w, 0) + 1
        self.idf = {w: math.log((n_docs + 1) / (count + 1)) + 1.0 for w, count in df.items()}

    def search(self, query: str, top_k: int = 3):
        q_tokens = self._tokenize(query)
        if not q_tokens or not self.corpus:
            return []

        scores = []
        for idx, tokens in enumerate(self.doc_tokens):
            if not tokens:
                scores.append((0.0, idx))
                continue
            score = 0.0
            n_tokens = len(tokens)
            for qt in q_tokens:
                if qt in tokens:
                    tf = tokens.count(qt) / n_tokens
                    idf_val = self.idf.get(qt, 1.0)
                    score += tf * idf_val
            scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, idx in scores[:top_k]:
            if score > 0.0:
                results.append(self.corpus[idx])
        return results


class NyxRetriever:
    """Retrieval-Augmented Generation (RAG) engine for SnowOS."""
    
    def __init__(self, memory_engine):
        self.memory = memory_engine
        self.logger = logging.getLogger("SnowOS.Retriever")
        
        # Try configured/home path first, then local repo path
        default_kb = os.path.expanduser("~/.snowos/nyx/learning/knowledge_base/system_knowledge.json")
        local_kb = os.path.join(os.path.dirname(__file__), "knowledge_base/system_knowledge.json")
        self.kb_path = default_kb if os.path.exists(default_kb) else local_kb
        
        if _SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(stop_words='english')
        else:
            self.vectorizer = None

        self._load_kb()

    def _load_kb(self):
        """Index the static knowledge base."""
        try:
            if os.path.exists(self.kb_path):
                with open(self.kb_path, 'r') as f:
                    self.kb = json.load(f)
            else:
                self.kb = {}
            
            self.base_corpus = []
            # Index modules
            for name, desc in self.kb.get("modules", {}).items():
                self.base_corpus.append(f"Module {name}: {desc}")
                
            # Index commands
            for cmd, ctx in self.kb.get("command_context", {}).items():
                self.base_corpus.append(f"Command '{cmd}': {ctx}")
        except Exception as e:
            self.logger.error("Failed to load KB: %s", e)
            self.kb = {}
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

            if not _SKLEARN_AVAILABLE:
                ranker = _PurePythonTfidf()
                ranker.fit(dynamic_corpus)
                return ranker.search(query, top_k=top_k)

            # 2. Vectorize and Search with Scikit-Learn
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
            self.logger.error("Retrieval error: %s", e)
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
