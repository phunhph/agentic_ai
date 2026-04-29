"""Vector memory abstraction with fallback in-memory store.

Provides: VectorMemory.add(text, metadata) and VectorMemory.query(query, top_k)
"""
from typing import List, Dict


class VectorMemory:
    def __init__(self, embedding_model_name: str = 'all-MiniLM-L6-v2'):
        # lightweight init — avoid importing heavy libs here
        self._items: List[Dict] = []
        self._embeddings = None
        self._index = None
        self._embedder = None
        self._embedding_model_name = embedding_model_name
        self._embedder_available = None  # None = unknown, False = unavailable, True = available

    def _ensure_embedder(self):
        # Lazy import heavy dependencies only when needed
        if self._embedder_available is not None:
            return self._embedder_available

        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            import faiss
            self._np = numpy = np
            self._faiss = faiss
            self._embedder = SentenceTransformer(self._embedding_model_name)
            self._embedder_available = True
        except Exception:
            # mark unavailable and proceed with lightweight fallback
            self._embedder_available = False
        return self._embedder_available

    def add(self, text: str, metadata: Dict = None):
        metadata = metadata or {}
        entry = {"text": text, "metadata": metadata}
        self._items.append(entry)
        # If embedding available, update index
        if self._ensure_embedder():
            vec = self._embedder.encode([text])
            if self._index is None:
                dim = len(vec[0])
                self._index = self._faiss.IndexFlatL2(dim)
                self._embeddings = vec
                self._index.add(vec)
            else:
                self._index.add(vec)
                self._embeddings = self._np.vstack([self._embeddings, vec])

    def query(self, query_text: str, top_k: int = 5):
        """Return top_k items (text, metadata, score) similar to query_text."""
        if self._ensure_embedder() and self._index is not None:
            qvec = self._embedder.encode([query_text])
            D, I = self._index.search(qvec, top_k)
            results = []
            for dist, idx in zip(D[0], I[0]):
                if idx < len(self._items):
                    results.append({"text": self._items[idx]['text'], "metadata": self._items[idx]['metadata'], "score": float(dist)})
            return results

        # Fallback: simple substring match ranking
        res = []
        qt = query_text.lower()
        for item in self._items:
            score = 0
            if qt in item['text'].lower():
                score = 1
            res.append({"text": item['text'], "metadata": item['metadata'], "score": score})
        res = sorted(res, key=lambda r: r['score'], reverse=True)
        return res[:top_k]
