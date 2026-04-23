from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class V2Metadata:
    tables: set[str]
    lookup_edges: set[tuple[str, str]]
    table_fields: dict[str, set[str]]


def load_v2_metadata(db_json_path: str = "db.json") -> V2Metadata:
    path = Path(db_json_path)
    if not path.exists():
        return V2Metadata(tables=set(), lookup_edges=set(), table_fields={})
    raw = json.loads(path.read_text(encoding="utf-8"))
    tables = {str(t.get("name", "")).strip() for t in raw.get("tables", []) if isinstance(t, dict)}
    table_fields: dict[str, set[str]] = {}
    for t in raw.get("tables", []) or []:
        if not isinstance(t, dict):
            continue
        table_name = str(t.get("name", "")).strip()
        if not table_name:
            continue
        fields = {
            str(f.get("name", "")).strip()
            for f in (t.get("fields", []) or [])
            if isinstance(f, dict) and str(f.get("name", "")).strip()
        }
        table_fields[table_name] = fields
    lookup_edges: set[tuple[str, str]] = set()
    for rel in raw.get("relations", {}).get("lookup", []) or []:
        if not isinstance(rel, dict):
            continue
        from_table = str(rel.get("from_table", "")).strip()
        to_table = str(rel.get("to_table", "")).strip()
        if from_table and to_table:
            lookup_edges.add((from_table, to_table))
            lookup_edges.add((to_table, from_table))
    return V2Metadata(tables=tables, lookup_edges=lookup_edges, table_fields=table_fields)
