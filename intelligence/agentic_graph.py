"""
intelligence/agentic_graph.py
Move từ DANN/core/agentic_graph.py — Agentic Graph cho DANN intelligence layer.
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, UTC

STORAGE_PATH = Path("storage/v2/dann/agentic_graph.json")


class AgenticGraph:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if STORAGE_PATH.exists():
            try:
                data = json.loads(STORAGE_PATH.read_text(encoding="utf-8"))
                self.nodes = data.get("nodes", {})
                self.edges = data.get("edges", [])
            except Exception as e:
                print(f"Error loading Agentic Graph: {str(e)}")

    def save(self):
        STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": datetime.now(UTC).strftime("dann-graph-%Y%m%d%H%M%S"),
            "nodes": self.nodes,
            "edges": self.edges,
            "updated_at": datetime.now(UTC).isoformat()
        }
        STORAGE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_relationship(self, node_a: str, node_b: str, relation_type: str, strength_delta: float):
        # Ensure nodes exist
        for node_id in [node_a, node_b]:
            if node_id not in self.nodes:
                self.nodes[node_id] = {"id": node_id, "support": 1}
            else:
                self.nodes[node_id]["support"] += 1

        # Find or create edge
        edge_found = False
        for edge in self.edges:
            if edge["from"] == node_a and edge["to"] == node_b and edge["type"] == relation_type:
                edge["weight"] = max(0.0, min(1.0, edge.get("weight", 0.5) + strength_delta))
                edge["support"] = edge.get("support", 0) + 1
                edge_found = True
                break

        if not edge_found:
            self.edges.append({
                "from": node_a,
                "to": node_b,
                "type": relation_type,
                "weight": max(0.0, min(1.0, 0.5 + strength_delta)),
                "support": 1
            })

        self.save()

    def get_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.edges if e["from"] == node_id]

    def get_relationship_strength(self, node_a: str, node_b: str) -> float:
        for edge in self.edges:
            if edge["from"] == node_a and edge["to"] == node_b:
                return edge.get("weight", 0.0)
        return 0.0

    def get_coverage(self) -> float:
        if not self.nodes:
            return 0.0
        # Simple coverage metric based on edge density
        return min(1.0, len(self.edges) / (len(self.nodes) * 2.0 if len(self.nodes) > 1 else 1))
