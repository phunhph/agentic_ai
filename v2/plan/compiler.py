import re

from v2.contracts import ExecutionPlan, IngestResult, RequestFilter
from v2.metadata import MetadataProvider

_PROVIDER = MetadataProvider()


def _pick_revenue_field(table_name: str) -> str | None:
    fields = _PROVIDER.get_fields(table_name)
    if not fields:
        return None
    priorities = [
        "estimated_value",
        "revenue",
        "amount",
        "total_value",
        "total_amount",
        "value",
        "budget",
    ]
    lowered_map = {str(f).lower(): str(f) for f in fields}
    for token in priorities:
        for lf, orig in lowered_map.items():
            if token == lf or token in lf:
                return orig
    return None


def _build_aggregate_ops(ingest: IngestResult, root_table: str, include_tables: list[str]) -> list[dict]:
    text = str(getattr(ingest, "normalized_query", "") or "").lower()
    aggregate_phrase_markers = ["thống kê", "thong ke", "bao cao", "báo cáo", "số lượng", "so luong", "doanh thu", "revenue"]
    aggregate_word_markers = ["count", "sum"]
    has_aggregate_signal = any(t in text for t in aggregate_phrase_markers) or any(
        re.search(rf"\b{re.escape(w)}\b", text) for w in aggregate_word_markers
    )
    if str(getattr(ingest, "intent", "")).strip().lower() != "analyze" or not has_aggregate_signal:
        return []

    ops: list[dict] = []
    entities = [e for e in ingest.entities if _PROVIDER.is_valid_table(e)]
    if not entities:
        entities = [root_table]

    wants_count = any(t in text for t in ["số lượng", "so luong"]) or bool(re.search(r"\bcount\b", text))
    wants_revenue = any(t in text for t in ["doanh thu", "revenue"]) or bool(re.search(r"\bsum\b", text))
    if not wants_count and not wants_revenue:
        wants_count = True

    if wants_count:
        for table in sorted(set(entities)):
            clean = table.replace("hbl_", "")
            ops.append({"type": "count", "table": table, "alias": f"{clean}_count"})

    if wants_revenue:
        # Dynamic candidate order: entity tables -> joined tables -> root -> remaining metadata tables.
        candidate_tables = []
        for t in entities + include_tables + [root_table] + _PROVIDER.get_all_tables():
            tt = str(t or "").strip()
            if tt and tt not in candidate_tables:
                candidate_tables.append(tt)
        for table in candidate_tables:
            if not _PROVIDER.is_valid_table(table):
                continue
            revenue_field = _pick_revenue_field(table)
            if revenue_field:
                clean = table.replace("hbl_", "")
                ops.append({"type": "sum", "table": table, "field": revenue_field, "alias": f"{clean}_revenue"})
                break
    return ops


def compile_execution_plan(ingest: IngestResult, reason_result: dict) -> ExecutionPlan:
    decision = reason_result.get("decision", {}) if isinstance(reason_result, dict) else {}
    args = decision.get("args", {}) if isinstance(decision, dict) else {}
    trace = decision.get("trace", {}) if isinstance(decision, dict) else {}

    root_table = str(args.get("root_table") or "")
    if not root_table:
        all_tables = _PROVIDER.get_all_tables()
        for entity in ingest.entities:
            if entity in all_tables:
                root_table = entity
                break
    if not root_table:
        root_table = _PROVIDER.get_default_root_table()

    join_path = trace.get("join_path", []) if isinstance(trace, dict) else []
    include_tables = [j.get("to_table") for j in join_path if isinstance(j, dict) and j.get("to_table")]

    where_filters: list[RequestFilter] = []
    for f in ingest.request_filters:
        where_filters.append(
            RequestFilter(
                field=_PROVIDER.normalize_filter_field(root_table, f.field),
                op=f.op,
                value=f.value,
            )
        )
    keyword = str(args.get("keyword", "") or "").strip()
    aggregate_ops = _build_aggregate_ops(ingest, root_table, include_tables)
    if aggregate_ops:
        keyword = ""
        where_filters = []
    if keyword and not where_filters:
        # Build a deterministic keyword filter so preview/runtime and learning
        # both reflect the intended WHERE constraint instead of empty filters.
        default_field = _PROVIDER.resolve_identity_field(root_table) or "keyword"
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
        update_data=args.get("update_data", {}) if isinstance(args.get("update_data"), dict) else {},
        aggregate_ops=aggregate_ops,
        limit=limit,
        include_tables=include_tables,
        keyword=keyword,
        tactical_context=args.get("tactical_context", {}) if isinstance(args.get("tactical_context"), dict) else {},
    )
