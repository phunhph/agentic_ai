from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from v2.contracts import LessonOutcome

LESSON_LOG_PATH = Path("storage/v2/lessons/lesson_log_v2.jsonl")


def _score_breakdown(outcome: LessonOutcome) -> dict[str, float]:
    plan = outcome.execution_plan
    join_score = 1.0 if plan.join_path else 0.5
    filter_score = 1.0 if plan.where_filters else 0.5
    shape_score = 1.0 if outcome.success else 0.0
    total = round((join_score + filter_score + shape_score) / 3.0, 4)
    return {
        "join_correctness": join_score,
        "filter_fidelity": filter_score,
        "result_shape": shape_score,
        "total": total,
    }


def record_outcome(outcome: LessonOutcome) -> dict:
    LESSON_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(outcome)
    payload["score_breakdown"] = _score_breakdown(outcome)
    payload["logged_at"] = datetime.now(UTC).isoformat()
    with LESSON_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload
