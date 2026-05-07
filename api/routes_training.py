"""
api/routes_training.py
Routes cho training và training overview.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_jsonl_samples(path: Path, limit: int = 10) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    # Latest runtime samples first
    return list(reversed(out))[:limit]


def _iso_mtime(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    except Exception:
        return ""


def _read_latest_auto_train_summary() -> dict:
    logs_dir = Path("storage/v2/training/auto_train_logs")
    if not logs_dir.exists():
        return {}
    summaries = sorted(logs_dir.glob("*_summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not summaries:
        return {}
    latest = summaries[0]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@router.post("/api/v2/train")
async def train_v2():
    try:
        from pipeline.phase5_learn.matrix import train_matrix_v2
        artifact = train_matrix_v2()
        return {"ok": True, "artifact": artifact}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/v2/training/overview")
async def v2_training_overview(sample_limit: int = 10):
    trainset_path = Path("storage/v2/matrix/trainset_v2.jsonl")
    matrix_artifact_path = Path("storage/v2/matrix/matrix_v2_artifact.json")
    matrix_eval_path = Path("storage/v2/matrix/matrix_v2_eval.json")
    graph_artifact_path = Path("storage/v2/graph/knowledge_graph_v2.json")
    graph_eval_path = Path("storage/v2/graph/knowledge_graph_v2_eval.json")

    train_samples = _read_jsonl_samples(trainset_path, limit=max(1, min(sample_limit, 50)))
    matrix_artifact = _read_json_file(matrix_artifact_path)
    matrix_eval = _read_json_file(matrix_eval_path)
    graph_artifact = _read_json_file(graph_artifact_path)
    graph_eval = _read_json_file(graph_eval_path)
    latest_auto_train = _read_latest_auto_train_summary()

    graph_nodes = graph_artifact.get("nodes", []) if isinstance(graph_artifact.get("nodes"), list) else []
    graph_edges = graph_artifact.get("edges", []) if isinstance(graph_artifact.get("edges"), list) else []
    graph_nodes_sorted = sorted(
        [n for n in graph_nodes if isinstance(n, dict)],
        key=lambda n: float(n.get("support", 0) or 0),
        reverse=True,
    )
    graph_edges_sorted = sorted(
        [e for e in graph_edges if isinstance(e, dict)],
        key=lambda e: float(e.get("support", 0) or 0),
        reverse=True,
    )

    return {
        "status": "ok",
        "files": {
            "trainset_exists": trainset_path.exists(),
            "matrix_artifact_exists": matrix_artifact_path.exists(),
            "matrix_eval_exists": matrix_eval_path.exists(),
            "graph_artifact_exists": graph_artifact_path.exists(),
            "graph_eval_exists": graph_eval_path.exists(),
            "trainset_mtime": _iso_mtime(trainset_path),
            "matrix_artifact_mtime": _iso_mtime(matrix_artifact_path),
            "matrix_eval_mtime": _iso_mtime(matrix_eval_path),
        },
        "runtime_training": {
            "latest_auto_train_summary": latest_auto_train,
        },
        "matrix": {
            "artifact": matrix_artifact,
            "eval": matrix_eval,
        },
        "graph": {
            "artifact_meta": {
                "version": graph_artifact.get("version"),
                "node_count": graph_artifact.get("node_count", 0),
                "edge_count": graph_artifact.get("edge_count", 0),
            },
            "eval": graph_eval,
            "top_nodes": graph_nodes_sorted[:10],
            "top_edges": graph_edges_sorted[:10],
        },
        "trainset_preview": {
            "sample_count": len(train_samples),
            "samples": train_samples,
        },
    }
