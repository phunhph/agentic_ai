from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from storage.schema_loader import load_schema_spec


@dataclass(frozen=True)
class GraphEdge:
    from_table: str
    to_table: str
    relation_type: str
    join_table: str | None = None
    from_field: str | None = None
    to_field: str | None = None
    choice_group: str | None = None


class MetadataProvider:
    """Read metadata from db.json (+ optional dbfi.json) and expose lookup APIs."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self._root_dir = root_dir or Path(__file__).resolve().parent.parent
        self._schema = load_schema_spec(self._root_dir / "db.json")
        self._dbfi = self._load_optional_dbfi()

        self._table_display = self._build_table_display()
        self._field_display = self._build_field_display()
        self._choice_label_to_code = self._build_choice_dictionary()
        self._graph = self._build_graph()
        self._aliases = self._build_aliases()

    def _load_optional_dbfi(self) -> dict:
        dbfi_path = self._root_dir / "dbfi.json"
        if not dbfi_path.exists():
            return {}
        try:
            return json.loads(dbfi_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _build_table_display(self) -> dict[str, str]:
        fallback = {t.name: t.name for t in self._schema.tables}
        table_meta = self._dbfi.get("tables")
        if not isinstance(table_meta, list):
            return fallback
        for item in table_meta:
            if not isinstance(item, dict):
                continue
            table_name = str(item.get("name", "")).strip()
            display_name = str(item.get("display_name", "")).strip()
            if table_name and display_name:
                fallback[table_name] = display_name
        return fallback

    def _build_field_display(self) -> dict[tuple[str, str], str]:
        mapping: dict[tuple[str, str], str] = {}
        tables = self._dbfi.get("tables")
        if not isinstance(tables, list):
            return mapping
        for table in tables:
            table_name = str(table.get("name", "")).strip()
            fields = table.get("fields")
            if not table_name or not isinstance(fields, list):
                continue
            for field in fields:
                if not isinstance(field, dict):
                    continue
                field_name = str(field.get("name", "")).strip()
                display_name = str(field.get("display_name", "")).strip()
                if field_name and display_name:
                    mapping[(table_name, field_name)] = display_name
        return mapping

    def _build_choice_dictionary(self) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for group, options in self._schema.choice_options.items():
            out[group] = {}
            for option in options:
                label = str(option.get("label", "")).strip()
                code = str(option.get("code", "")).strip()
                if label and code:
                    out[group][label.lower()] = code
        return out

    def _build_graph(self) -> dict[str, list[GraphEdge]]:
        graph: dict[str, list[GraphEdge]] = {}

        def add_edge(table_name: str, edge: GraphEdge) -> None:
            graph.setdefault(table_name, []).append(edge)

        for rel in self._schema.lookup_relations:
            edge_fw = GraphEdge(
                from_table=rel.from_table,
                to_table=rel.to_table,
                relation_type="lookup",
                from_field=rel.from_field,
                to_field=rel.to_field,
            )
            edge_bw = GraphEdge(
                from_table=rel.to_table,
                to_table=rel.from_table,
                relation_type="lookup",
                from_field=rel.to_field,
                to_field=rel.from_field,
            )
            add_edge(rel.from_table, edge_fw)
            add_edge(rel.to_table, edge_bw)

        for rel in self._schema.choice_relations:
            edge_fw = GraphEdge(
                from_table=rel.left_table,
                to_table=rel.right_table,
                relation_type="choice",
                join_table=rel.join_table,
                from_field=rel.left_fk,
                to_field=rel.right_fk,
                choice_group=rel.right_group,
            )
            edge_bw = GraphEdge(
                from_table=rel.right_table,
                to_table=rel.left_table,
                relation_type="choice",
                join_table=rel.join_table,
                from_field=rel.right_fk,
                to_field=rel.left_fk,
                choice_group=rel.right_group,
            )
            add_edge(rel.left_table, edge_fw)
            add_edge(rel.right_table, edge_bw)

        return graph

    def _build_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for table in self._schema.tables:
            aliases[table.name.lower()] = table.name
            aliases[table.name.replace("hbl_", "").lower()] = table.name
        aliases.update(
            {
                "khach hang": "hbl_account",
                "khách hàng": "hbl_account",
                "account": "hbl_account",
                "contact": "hbl_contact",
                "lien he": "hbl_contact",
                "liên hệ": "hbl_contact",
                "opportunity": "hbl_opportunities",
                "opportunities": "hbl_opportunities",
                "ops": "hbl_opportunities",
                "hop dong": "hbl_contract",
                "hợp đồng": "hbl_contract",
                "contract": "hbl_contract",
                "sales": "systemuser",
                "user": "systemuser",
            }
        )
        return aliases

    def get_table_display(self, table_name: str) -> str:
        return self._table_display.get(table_name, table_name)

    def get_field_display(self, table_name: str, field_name: str) -> str:
        return self._field_display.get((table_name, field_name), field_name)

    def resolve_alias(self, term: str) -> str | None:
        return self._aliases.get((term or "").strip().lower())

    def resolve_choice_code(self, group: str, label: str) -> str | None:
        return self._choice_label_to_code.get(group, {}).get((label or "").strip().lower())

    def expand_choice_filter(self, left_table: str, group: str, label: str) -> dict | None:
        code = self.resolve_choice_code(group, label)
        if not code:
            return None
        for rel in self._schema.choice_relations:
            if rel.left_table == left_table and rel.right_group == group:
                return {
                    "left_table": rel.left_table,
                    "join_table": rel.join_table,
                    "right_table": rel.right_table,
                    "left_fk": rel.left_fk,
                    "right_fk": rel.right_fk,
                    "choice_group": group,
                    "choice_code": code,
                    "choice_label": label,
                }
        return None

    def find_paths(self, source_table: str, target_table: str, max_depth: int = 4) -> list[list[GraphEdge]]:
        if source_table == target_table:
            return [[]]
        if source_table not in self._graph or target_table not in self._graph:
            return []

        queue: deque[tuple[str, list[GraphEdge]]] = deque([(source_table, [])])
        visited_depth: dict[str, int] = {source_table: 0}
        paths: list[list[GraphEdge]] = []
        shortest_len: int | None = None

        while queue:
            node, path = queue.popleft()
            if shortest_len is not None and len(path) > shortest_len:
                continue
            if len(path) > max_depth:
                continue
            if node == target_table:
                shortest_len = len(path) if shortest_len is None else shortest_len
                paths.append(path)
                continue
            for edge in self._graph.get(node, []):
                next_depth = len(path) + 1
                prev_depth = visited_depth.get(edge.to_table)
                if prev_depth is not None and prev_depth < next_depth:
                    continue
                visited_depth[edge.to_table] = next_depth
                queue.append((edge.to_table, [*path, edge]))
        return paths


_PROVIDER: MetadataProvider | None = None


def get_metadata_provider() -> MetadataProvider:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = MetadataProvider()
    return _PROVIDER

