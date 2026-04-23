from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from v2.learn.graph import evaluate_knowledge_graph_v2, train_knowledge_graph_v2
from v2.learn.trainset import bootstrap_trainset_from_cases

TRAINSET_PATH = Path("storage/v2/matrix/trainset_v2.jsonl")
ARTIFACT_PATH = Path("storage/v2/matrix/matrix_v2_artifact.json")
EVAL_PATH = Path("storage/v2/matrix/matrix_v2_eval.json")


def _read_trainset_rows() -> list[dict]:
    if not TRAINSET_PATH.exists():
        return []
    rows: list[dict] = []
    for line in TRAINSET_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    # Anti-rote aggregation: keep one row per semantic signature.
    dedup: dict[str, dict] = {}
    fallback_idx = 0
    for row in rows:
        signature = str(row.get("signature", "")).strip()
        if not signature:
            signature = f"fallback:{fallback_idx}"
            fallback_idx += 1
        prev = dedup.get(signature)
        if prev is None:
            dedup[signature] = row
            continue
        # Prefer successful evidence over failed evidence for same signature.
        if bool(row.get("success_label", False)) and not bool(prev.get("success_label", False)):
            dedup[signature] = row
    return list(dedup.values())


def train_matrix_v2() -> dict:
    TRAINSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TRAINSET_PATH.exists() or not TRAINSET_PATH.read_text(encoding="utf-8").strip():
        bootstrap_trainset_from_cases()
    if not TRAINSET_PATH.exists():
        TRAINSET_PATH.write_text("", encoding="utf-8")
    lines = [x for x in TRAINSET_PATH.read_text(encoding="utf-8").splitlines() if x.strip()]
    artifact = {
        "version": datetime.now(UTC).strftime("v2-%Y%m%d%H%M%S"),
        "train_samples": len(lines),
        "trained_at": datetime.now(UTC).isoformat(),
    }
    graph_artifact = train_knowledge_graph_v2()
    artifact["knowledge_graph"] = {
        "version": graph_artifact.get("version"),
        "node_count": graph_artifact.get("node_count", 0),
        "edge_count": graph_artifact.get("edge_count", 0),
    }
    ARTIFACT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def evaluate_matrix_v2() -> dict:
    artifact = {"version": "missing", "train_samples": 0}
    if ARTIFACT_PATH.exists():
        artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    rows = _read_trainset_rows()
    total = len(rows)
    success_values = [1.0 if bool(r.get("success_label", False)) else 0.0 for r in rows]
    tool_plan_correctness = (sum(success_values) / total) if total else 0.0

    filter_rows = [r for r in rows if isinstance(r.get("filters"), list) and len(r.get("filters")) > 0]
    if filter_rows:
        filter_success = [1.0 if bool(r.get("success_label", False)) else 0.0 for r in filter_rows]
        filter_fidelity = sum(filter_success) / len(filter_success)
    else:
        filter_fidelity = tool_plan_correctness

    join_rows = [r for r in rows if isinstance(r.get("join_plan"), list) and len(r.get("join_plan")) > 0]
    if join_rows:
        join_success = [1.0 if bool(r.get("success_label", False)) else 0.0 for r in join_rows]
        join_correctness = sum(join_success) / len(join_success)
    else:
        join_correctness = tool_plan_correctness

    unique_intents = {str(r.get("intent", "unknown")).strip().lower() for r in rows}
    unique_tables = {str(r.get("root_table", "")).strip() for r in rows if str(r.get("root_table", "")).strip()}
    diversity_score = min(1.0, ((len(unique_intents) / 5.0) + (len(unique_tables) / 5.0)) / 2.0) if total else 0.0
    report = {
        "version": artifact.get("version"),
        "train_samples": artifact.get("train_samples", 0),
        "tool_plan_correctness": round(tool_plan_correctness, 4),
        "filter_fidelity": round(filter_fidelity, 4),
        "join_correctness": round(join_correctness, 4),
        "training_diversity": round(diversity_score, 4),
    }
    graph_report = evaluate_knowledge_graph_v2()
    report["graph_coverage"] = float(graph_report.get("coverage", 0.0))
    report["graph_node_count"] = int(graph_report.get("node_count", 0))
    report["graph_edge_count"] = int(graph_report.get("edge_count", 0))
    EVAL_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
