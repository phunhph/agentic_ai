from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from DANN.core.agentic_graph import AgenticGraph

TRAINSET_PATH = Path("storage/v2/matrix/trainset_v2.jsonl")
GRAPH_ARTIFACT_PATH = Path("storage/v2/graph/knowledge_graph_v2.json")
GRAPH_EVAL_PATH = Path("storage/v2/graph/knowledge_graph_v2_eval.json")

_GRAPH = AgenticGraph()

def train_knowledge_graph_v2() -> dict:
    if TRAINSET_PATH.exists():
        for line in TRAINSET_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            try:
                sample = json.loads(line)
                intent = str(sample.get("intent", "unknown")).strip().lower() or "unknown"
                root_table = str(sample.get("root_table", "hbl_account")).strip() or "hbl_account"
                expected_tool = str((sample.get("expected_shape") or {}).get("expected_tool", "unknown")).strip().lower() or "unknown"
                success = bool(sample.get("success_label", True))
                
                delta = 0.05 if success else -0.1
                
                _GRAPH.update_relationship(f"intent:{intent}", f"table:{root_table}", "maps_to", delta)
                _GRAPH.update_relationship(f"table:{root_table}", f"tool:{expected_tool}", "served_by", delta)
                _GRAPH.update_relationship(f"intent:{intent}", f"tool:{expected_tool}", "selects", delta)
            except Exception:
                continue

    artifact = {
        "version": datetime.now(UTC).strftime("dann-graph-%Y%m%d%H%M%S"),
        "trained_at": datetime.now(UTC).isoformat(),
        "node_count": len(_GRAPH.nodes),
        "edge_count": len(_GRAPH.edges),
        "nodes": list(_GRAPH.nodes.values()),
        "edges": _GRAPH.edges,
    }
    
    GRAPH_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_ARTIFACT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def evaluate_knowledge_graph_v2() -> dict:
    coverage = _GRAPH.get_coverage()
    report = {
        "version": datetime.now(UTC).strftime("dann-graph-eval-%H%M%S"),
        "node_count": len(_GRAPH.nodes),
        "edge_count": len(_GRAPH.edges),
        "coverage": round(coverage, 4),
        "structure_score": 1.0 if len(_GRAPH.nodes) > 5 else 0.5,
        "relation_score": round(min(1.0, len(_GRAPH.edges) / 20.0), 4),
        "density_score": round(coverage, 4),
    }
    
    GRAPH_EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_EVAL_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def get_path_strength(intent: str, table: str, tool: str) -> float:
    """Evaluate the strength of a reasoning path using the Agentic Graph."""
    s1 = _GRAPH.get_relationship_strength(f"intent:{intent}", f"table:{table}")
    s2 = _GRAPH.get_relationship_strength(f"table:{table}", f"tool:{tool}")
    return (s1 + s2) / 2.0
