from __future__ import annotations

import json
from pathlib import Path

from infra.settings import (
    V2_GATE_MIN_FILTER_FIDELITY,
    V2_GATE_MIN_JOIN_CORRECTNESS,
    V2_GATE_MIN_PLAN_CORRECTNESS,
)

EVAL_PATH = Path("storage/v2/matrix/matrix_v2_eval.json")
GATE_PATH = Path("storage/v2/gate/feasibility_gate.json")


def evaluate_feasibility_gate() -> dict:
    metrics = {
        "tool_plan_correctness": 0.0,
        "filter_fidelity": 0.0,
        "join_correctness": 0.0,
        "graph_coverage": 0.0,
    }
    if EVAL_PATH.exists():
        raw = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
        metrics["tool_plan_correctness"] = float(raw.get("tool_plan_correctness", 0.0))
        metrics["filter_fidelity"] = float(raw.get("filter_fidelity", 0.0))
        metrics["join_correctness"] = float(raw.get("join_correctness", metrics["tool_plan_correctness"]))
        metrics["graph_coverage"] = float(raw.get("graph_coverage", 0.0))

    passed = (
        metrics["tool_plan_correctness"] >= V2_GATE_MIN_PLAN_CORRECTNESS
        and metrics["filter_fidelity"] >= V2_GATE_MIN_FILTER_FIDELITY
        and metrics["join_correctness"] >= V2_GATE_MIN_JOIN_CORRECTNESS
        and metrics["graph_coverage"] >= 0.8
    )
    result = {
        "passed": passed,
        "metrics": metrics,
        "thresholds": {
            "tool_plan_correctness": V2_GATE_MIN_PLAN_CORRECTNESS,
            "filter_fidelity": V2_GATE_MIN_FILTER_FIDELITY,
            "join_correctness": V2_GATE_MIN_JOIN_CORRECTNESS,
            "graph_coverage": 0.8,
        },
        "action": "promote_v2" if passed else "rollback_to_v1",
    }
    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
