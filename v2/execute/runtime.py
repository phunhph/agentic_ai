from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from storage.database import engine
from v2.contracts import ExecutionPlan, ExecutionResult
from v2.execute.validator import validate_execution_plan


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _load_lookup_relations() -> list[dict[str, str]]:
    path = Path("db.json")
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for rel in (raw.get("relations", {}).get("lookup", []) or []):
        if not isinstance(rel, dict):
            continue
        from_table = str(rel.get("from_table", "")).strip()
        from_field = str(rel.get("from_field", "")).strip()
        to_table = str(rel.get("to_table", "")).strip()
        to_field = str(rel.get("to_field", "")).strip()
        if from_table and from_field and to_table and to_field:
            out.append(
                {
                    "from_table": from_table,
                    "from_field": from_field,
                    "to_table": to_table,
                    "to_field": to_field,
                }
            )
    return out


def _build_relation_graph(relations: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    graph: dict[str, list[dict[str, str]]] = {}
    for rel in relations:
        src = rel["from_table"]
        dst = rel["to_table"]
        graph.setdefault(src, []).append(rel)
        graph.setdefault(dst, []).append(
            {
                "from_table": dst,
                "from_field": rel["to_field"],
                "to_table": src,
                "to_field": rel["from_field"],
            }
        )
    return graph


def _find_join_path(
    root_table: str,
    target_table: str,
    graph: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    if root_table == target_table:
        return []
    queue: list[tuple[str, list[dict[str, str]]]] = [(root_table, [])]
    visited = {root_table}
    idx = 0
    while idx < len(queue):
        current, path = queue[idx]
        idx += 1
        for hop in graph.get(current, []):
            nxt = hop["to_table"]
            if nxt in visited:
                continue
            new_path = path + [hop]
            if nxt == target_table:
                return new_path
            visited.add(nxt)
            queue.append((nxt, new_path))
    return []


def _guess_label_columns(table: sa.Table) -> list[sa.Column]:
    picked: list[sa.Column] = []
    for col_name in table.columns.keys():
        lc = str(col_name).lower()
        if lc.endswith("_name") or lc in {"name", "full_name", "fullname"} or "label" in lc:
            picked.append(table.c[col_name])
    if not picked:
        return []
    picked.sort(key=lambda c: (0 if str(c.name).lower().endswith("_name") else 1, len(str(c.name))))
    return picked[:2]


def _resolve_filter_column(root_table: str, raw_field: str, table_map: dict[str, sa.Table]) -> sa.Column:
    field = str(raw_field or "").strip()
    if "." in field:
        table_name, col_name = field.split(".", 1)
    else:
        table_name, col_name = root_table, field
    table = table_map[table_name]
    return table.c[col_name]


def _build_condition(col: sa.Column, op: str, value: Any):
    normalized_op = str(op or "").strip().lower()
    if normalized_op == "eq":
        if isinstance(value, str):
            # Text equality should be robust to casing differences from parser/LLM.
            return sa.func.lower(sa.cast(col, sa.String)) == value.strip().lower()
        return col == value
    if normalized_op == "contains":
        return sa.cast(col, sa.String).ilike(f"%{value}%")
    if normalized_op == "in":
        if isinstance(value, list):
            return col.in_(value)
        if isinstance(value, str):
            vals = [x.strip() for x in value.split(",") if x.strip()]
            return col.in_(vals)
        return col.in_([value])
    if normalized_op == "range":
        if isinstance(value, dict):
            left = value.get("min")
            right = value.get("max")
            if left is not None and right is not None:
                return col.between(left, right)
            if left is not None:
                return col >= left
            if right is not None:
                return col <= right
        if isinstance(value, list) and len(value) == 2:
            return col.between(value[0], value[1])
    # Fallback safe guard (should be blocked by validator anyway)
    return col == value


def execute_plan(plan: ExecutionPlan) -> ExecutionResult:
    validation = validate_execution_plan(plan)
    if not validation.ok:
        return ExecutionResult(
            data=[],
            success=False,
            execution_trace={
                "plan": asdict(plan),
                "guardrail": {"ok": False, "errors": validation.errors, "warnings": validation.warnings},
                "sql_summary": "blocked_before_query",
                "row_count": 0,
            },
        )

    metadata = sa.MetaData()
    table_map: dict[str, sa.Table] = {}
    root = sa.Table(plan.root_table, metadata, autoload_with=engine)
    table_map[plan.root_table] = root
    for f in plan.where_filters:
        field = str(f.field or "")
        if "." in field:
            t = field.split(".", 1)[0]
            if t not in table_map:
                table_map[t] = sa.Table(t, metadata, autoload_with=engine)

    select_cols: list[sa.Column] = [root.c[c] for c in root.columns.keys()]
    relations = _load_lookup_relations()
    graph = _build_relation_graph(relations)
    required_tables = set(table_map.keys()) | set(plan.include_tables or [])
    required_tables.discard(plan.root_table)

    from_clause = root
    joined_tables = {plan.root_table}
    join_edges: list[str] = []
    for target in sorted(required_tables):
        if target in joined_tables:
            continue
        path = _find_join_path(plan.root_table, target, graph)
        if not path:
            continue
        for hop in path:
            from_table = hop["from_table"]
            to_table = hop["to_table"]
            if to_table in joined_tables:
                continue
            if from_table not in table_map:
                table_map[from_table] = sa.Table(from_table, metadata, autoload_with=engine)
            if to_table not in table_map:
                table_map[to_table] = sa.Table(to_table, metadata, autoload_with=engine)
            left = table_map[from_table]
            right = table_map[to_table]
            from_clause = from_clause.join(
                right,
                left.c[hop["from_field"]] == right.c[hop["to_field"]],
                isouter=True,
            )
            joined_tables.add(to_table)
            join_edges.append(f"{from_table}.{hop['from_field']}={to_table}.{hop['to_field']}")
            for c in _guess_label_columns(right):
                select_cols.append(c.label(f"{to_table}__{c.name}"))

    stmt = sa.select(*select_cols).select_from(from_clause)
    conditions = []
    applied_filters = []
    for f in plan.where_filters:
        col = _resolve_filter_column(plan.root_table, f.field, table_map)
        cond = _build_condition(col, f.op, f.value)
        conditions.append(cond)
        applied_filters.append(asdict(f))
    if conditions:
        stmt = stmt.where(sa.and_(*conditions))
    if int(plan.limit) > 0:
        stmt = stmt.limit(int(plan.limit))

    with engine.connect() as conn:
        rows_raw = conn.execute(stmt).mappings().all()
    rows = [{k: _serialize_value(v) for k, v in dict(r).items()} for r in rows_raw]

    return ExecutionResult(
        data=rows,
        success=bool(rows),
        execution_trace={
            "plan": asdict(plan),
            "guardrail": {"ok": True, "errors": [], "warnings": validation.warnings},
            "sql_summary": str(stmt),
            "where_clause_simulated": applied_filters,
            "resolved_join_edges": join_edges,
            "row_count": len(rows),
            "raw_result": {"mode": "db_query"},
        },
    )
