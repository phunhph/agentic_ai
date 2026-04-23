from __future__ import annotations

from v2.contracts import ExecutionPlan, IngestResult, RequestFilter
from v2.metadata import load_v2_metadata


ENTITY_ROOT_HINTS = {
    "hbl_account": "hbl_account",
    "hbl_contact": "hbl_contact",
    "hbl_contract": "hbl_contract",
    "hbl_opportunities": "hbl_opportunities",
}


def _best_text_field(root_table: str, table_fields: dict[str, set[str]]) -> str | None:
    candidates = [
        f"{root_table}_name",
        "name",
    ]
    fields = table_fields.get(root_table, set())
    for c in candidates:
        if c in fields:
            return c
    # metadata-driven fallback: any *_name column
    for f in sorted(fields):
        if f.endswith("_name"):
            return f
    return None


def _resolve_column_alias(table_name: str, raw_col: str, table_fields: dict[str, set[str]]) -> str | None:
    col = str(raw_col or "").strip()
    if not col:
        return _best_text_field(table_name, table_fields)
    fields = table_fields.get(table_name, set())
    if col in fields:
        return col
    if col.lower() == "name":
        return _best_text_field(table_name, table_fields)
    # metadata-driven aliasing: map "foo" -> "*_foo" if unique
    candidates = [f for f in fields if f.endswith(f"_{col}")]
    if len(candidates) == 1:
        return candidates[0]
    # relaxed contains match as last resort
    contains = [f for f in fields if col in f]
    if len(contains) == 1:
        return contains[0]
    return None


def _normalize_filter_field(raw_field: str, root_table: str, table_fields: dict[str, set[str]]) -> str:
    field = str(raw_field or "").strip()
    if not field:
        best = _best_text_field(root_table, table_fields)
        return f"{root_table}.{best}" if best else f"{root_table}.keyword"
    if "." in field:
        table_name, col_name = field.split(".", 1)
        table_name = table_name.strip() or root_table
        col_name = col_name.strip()
        resolved = _resolve_column_alias(table_name, col_name, table_fields)
        if resolved:
            return f"{table_name}.{resolved}"
        best = _best_text_field(table_name, table_fields)
        return f"{table_name}.{best}" if best else f"{table_name}.keyword"
    resolved = _resolve_column_alias(root_table, field, table_fields)
    if resolved:
        return f"{root_table}.{resolved}"
    best = _best_text_field(root_table, table_fields)
    return f"{root_table}.{best}" if best else f"{root_table}.keyword"


def compile_execution_plan(ingest: IngestResult, reason_result: dict) -> ExecutionPlan:
    decision = reason_result.get("decision", {}) if isinstance(reason_result, dict) else {}
    args = decision.get("args", {}) if isinstance(decision, dict) else {}
    trace = decision.get("trace", {}) if isinstance(decision, dict) else {}

    root_table = str(args.get("root_table") or "")
    if not root_table:
        for entity in ingest.entities:
            if entity in ENTITY_ROOT_HINTS:
                root_table = ENTITY_ROOT_HINTS[entity]
                break
    if not root_table:
        root_table = "hbl_account"
    metadata = load_v2_metadata()

    join_path = trace.get("join_path", []) if isinstance(trace, dict) else []
    include_tables = [j.get("to_table") for j in join_path if isinstance(j, dict) and j.get("to_table")]

    where_filters: list[RequestFilter] = []
    for f in ingest.request_filters:
        where_filters.append(
            RequestFilter(
                field=_normalize_filter_field(f.field, root_table, metadata.table_fields),
                op=f.op,
                value=f.value,
            )
        )
    keyword = str(args.get("keyword", "") or "").strip()
    if keyword and not where_filters:
        # Build a deterministic keyword filter so preview/runtime and learning
        # both reflect the intended WHERE constraint instead of empty filters.
        default_field = _best_text_field(root_table, metadata.table_fields) or "keyword"
        where_filters = [
            RequestFilter(
                field=f"{root_table}.{default_field}",
                op="contains",
                value=keyword,
            )
        ]

    raw_limit = args.get("limit")
    limit = 0
    try:
        if raw_limit not in (None, ""):
            limit = max(0, int(raw_limit))
    except (TypeError, ValueError):
        limit = 0

    return ExecutionPlan(
        root_table=root_table,
        join_path=join_path if isinstance(join_path, list) else [],
        where_filters=where_filters,
        aggregate_ops=[],
        limit=limit,
        include_tables=include_tables,
        keyword=keyword,
    )
