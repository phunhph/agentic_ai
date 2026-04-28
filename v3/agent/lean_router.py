from __future__ import annotations
import json
import re
from pathlib import Path
from v2.learn.trainset import TRAINSET_PATH

class LeanRouter:
    """
    Optimization layer to bypass LLM calls if a similar query has been learned.
    Implements a 'Fast Path' using the training set.
    """
    
    def __init__(self, trainset_path: Path = TRAINSET_PATH):
        self.trainset_path = trainset_path
        self._cache = []
        self._load_cache()

    def _load_cache(self):
        self._cache = [] # Clear existing
        if not self.trainset_path.exists():
            return
        try:
            with self.trainset_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._cache.append(json.loads(line))
        except Exception:
            pass

    def match(self, query: str) -> dict | None:
        """
        Try to find a matching sample in the trainset.
        Returns the sample (intent, entities, filters) if found.
        """
        self._load_cache() # Always reload to ensure instant learning in dev mode
        q = str(query or "").strip().lower()
        # 1. Exact match on normalized query
        for sample in self._cache:
            if sample.get("normalized_query") == q and sample.get("success_label"):
                return sample
        
        # 2. Template match (replacing specific names with placeholders)
        q_template = self._gen_template(q)
        
        for sample in self._cache:
            if sample.get("query_template") == q_template and sample.get("success_label"):
                # Extract the dynamic part (the <text> placeholder)
                # For now, we'll try to find what changed between the template and original
                # A simple way: if the filter was 'MIMS' and the new query has 'ABC', replace it.
                new_sample = json.loads(json.dumps(sample))
                # Try to find potential entity name in the query that isn't in the template
                # This is a bit heuristic for 'Lean' mode
                words = q.split()
                learned_words = sample.get("query", "").lower().split()
                
                # Simple replacement logic for single-filter queries
                if len(new_sample.get("filters", [])) == 1:
                    old_val = new_sample["filters"][0].get("value")
                    if isinstance(old_val, str) and old_val.lower() in learned_words:
                        # Find the word in 'q' that is at the same relative position or just exists
                        # For now, let's look for words in 'q' that weren't in the learned core words
                        core_words = ["chi", "tiết", "về", "account", "là", "gì", "xem", "thông", "tin"]
                        potential_new_vals = [w for w in words if w not in core_words]
                        if potential_new_vals:
                            new_sample["filters"][0]["value"] = " ".join(potential_new_vals)
                
                return new_sample
                
        return None

    def _gen_template(self, query: str) -> str:
        q = query.lower().strip()
        # Replace numbers
        q = re.sub(r"\b\d+\b", "<num>", q)
        # Replace common CRM stop words to find the core pattern
        # This helps matching "xem chi tiết" vs "cho tôi xem chi tiết"
        q = q.replace("cho tôi ", "").replace("hãy ", "").replace("giúp tôi ", "")
        return q
