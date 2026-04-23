from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

TRAINSET_PATH = Path("storage/v2/matrix/trainset_v2.jsonl")
GRAPH_ARTIFACT_PATH = Path("storage/v2/graph/knowledge_graph_v2.json")
GRAPH_EVAL_PATH = Path("storage/v2/graph/knowledge_graph_v2_eval.json")


def _read_train_samples() -> list[dict]:
    if not TRAINSET_PATH.exists():
        return []
    samples: list[dict] = []
    for line in TRAINSET_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            samples.append(row)
    return samples


def train_knowledge_graph_v2() -> dict:
    samples = _read_train_samples()
    node_counts = Counter()
    edge_counts = Counter()

    for sample in samples:
        intent = str(sample.get("intent", "unknown")).strip().lower() or "unknown"
        root_table = str(sample.get("root_table", "hbl_account")).strip() or "hbl_account"
        expected_tool = str((sample.get("expected_shape") or {}).get("expected_tool", "unknown")).strip().lower() or "unknown"

        intent_node = f"intent:{intent}"
        table_node = f"table:{root_table}"
        tool_node = f"tool:{expected_tool}"

        node_counts[intent_node] += 1
        node_counts[table_node] += 1
        node_counts[tool_node] += 1

        edge_counts[(intent_node, table_node, "maps_to")] += 1
        edge_counts[(table_node, tool_node, "served_by")] += 1
        edge_counts[(intent_node, tool_node, "selects")] += 1

    artifact = {
        "version": datetime.now(UTC).strftime("v2-graph-%Y%m%d%H%M%S"),
        "trained_at": datetime.now(UTC).isoformat(),
        "node_count": len(node_counts),
        "edge_count": len(edge_counts),
        "nodes": [{"id": n, "support": c} for n, c in sorted(node_counts.items())],
        "edges": [
            {"from": a, "to": b, "type": rel, "weight": w}
            for (a, b, rel), w in sorted(edge_counts.items())
        ],
    }
    GRAPH_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_ARTIFACT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def evaluate_knowledge_graph_v2() -> dict:
    if not GRAPH_ARTIFACT_PATH.exists():
        report = {"coverage": 0.0, "node_count": 0, "edge_count": 0}
    else:
        graph = json.loads(GRAPH_ARTIFACT_PATH.read_text(encoding="utf-8"))
        node_count = int(graph.get("node_count", 0))
        edge_count = int(graph.get("edge_count", 0))
        nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
        edges = graph.get("edges", []) if isinstance(graph.get("edges"), list) else []
        intent_nodes = [n for n in nodes if isinstance(n, dict) and str(n.get("id", "")).startswith("intent:")]
        table_nodes = [n for n in nodes if isinstance(n, dict) and str(n.get("id", "")).startswith("table:")]
        tool_nodes = [n for n in nodes if isinstance(n, dict) and str(n.get("id", "")).startswith("tool:")]
        maps_edges = [e for e in edges if isinstance(e, dict) and str(e.get("type", "")) == "maps_to"]
        selects_edges = [e for e in edges if isinstance(e, dict) and str(e.get("type", "")) == "selects"]
        served_edges = [e for e in edges if isinstance(e, dict) and str(e.get("type", "")) == "served_by"]

        structure_score = 1.0 if intent_nodes and table_nodes and tool_nodes else 0.0
        relation_score = min(1.0, (len(maps_edges) + len(selects_edges) + len(served_edges)) / 12.0)
        density_score = min(1.0, edge_count / max(1.0, node_count * 2.0))
        coverage = round((structure_score * 0.4) + (relation_score * 0.4) + (density_score * 0.2), 4)
        report = {
            "version": graph.get("version", "unknown"),
            "node_count": node_count,
            "edge_count": edge_count,
            "coverage": coverage,
            "structure_score": round(structure_score, 4),
            "relation_score": round(relation_score, 4),
            "density_score": round(density_score, 4),
        }
    GRAPH_EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_EVAL_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
