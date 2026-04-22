from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from dynamic_metadata.paths import dynamic_cases_path
from dynamic_metadata.text_normalize import normalize_goal_text


def _tokenize(text: str) -> set[str]:
    normalized = normalize_goal_text(text)
    return {t.strip().lower() for t in normalized.split() if t.strip()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return inter / union if union else 0.0


def _coverage(goal_tokens: set[str], case_tokens: set[str]) -> float:
    if not goal_tokens or not case_tokens:
        return 0.0
    inter = len(goal_tokens.intersection(case_tokens))
    return inter / len(case_tokens)


@lru_cache(maxsize=1)
def load_cases() -> list[dict[str, Any]]:
    path = dynamic_cases_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def match_case(goal: str) -> dict[str, Any] | None:
    goal_tokens = _tokenize(goal)
    if not goal_tokens:
        return None
    best_case: dict[str, Any] | None = None
    best_score = 0.0
    for case in load_cases():
        query = str(case.get("query", "")).strip()
        if not query:
            continue
        case_tokens = _tokenize(query)
        score = max(_jaccard(goal_tokens, case_tokens), _coverage(goal_tokens, case_tokens))
        if score > best_score:
            best_score = score
            best_case = case
    if not best_case:
        return None
    return {"case": best_case, "similarity": round(best_score, 4)}

