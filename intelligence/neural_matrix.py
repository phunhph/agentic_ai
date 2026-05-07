"""
intelligence/neural_matrix.py
Move từ DANN/core/neural_matrix.py — Neural Matrix cho DANN intelligence layer.
"""
import json
import math
from pathlib import Path
from typing import List, Dict, Any

from clients.llm import get_dynamic_client

STORAGE_PATH = Path("storage/v2/dann/neural_matrix.json")


class NeuralMatrix:
    def __init__(self):
        self.samples: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if STORAGE_PATH.exists():
            try:
                self.samples = json.loads(STORAGE_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Error loading Neural Matrix: {str(e)}")
                self.samples = []

    def save(self):
        STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STORAGE_PATH.write_text(json.dumps(self.samples, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_sample(self, query: str, plan: Dict[str, Any], success: bool):
        client = get_dynamic_client("embedding")
        embedding = client.embed(query)

        if not embedding:
            return

        sample = {
            "query": query,
            "embedding": embedding,
            "plan": plan,
            "success": success,
            "intent": plan.get("intent"),
            "root_table": plan.get("root_table")
        }

        # Avoid exact duplicates in storage
        for s in self.samples:
            if s["query"] == query and s["plan"] == plan:
                s["success"] = success  # Update success status
                s["embedding"] = embedding
                self.save()
                return

        self.samples.append(sample)
        self.save()

    def find_similar(self, query: str, threshold: float = 0.85, top_k: int = 3) -> List[Dict[str, Any]]:
        client = get_dynamic_client("embedding")
        query_embedding = client.embed(query)

        if not query_embedding:
            return []

        results = []
        for sample in self.samples:
            similarity = self._cosine_similarity(query_embedding, sample["embedding"])
            if similarity >= threshold:
                results.append({
                    "sample": sample,
                    "similarity": round(similarity, 4)
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))

        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def get_diversity_score(self) -> float:
        if not self.samples:
            return 0.0
        unique_intents = {s.get("intent") for s in self.samples if s.get("intent")}
        unique_tables = {s.get("root_table") for s in self.samples if s.get("root_table")}
        return min(1.0, (len(unique_intents) + len(unique_tables)) / 20.0)

    def get_success_rate(self) -> float:
        if not self.samples:
            return 0.0
        successes = sum(1 for s in self.samples if s.get("success"))
        return successes / len(self.samples)
