from v2.contracts import ExecutionPlan, IngestResult, RequestFilter
from v2.metadata import MetadataProvider

_PROVIDER = MetadataProvider()


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
        aggregate_ops=[],
        limit=limit,
        include_tables=include_tables,
        keyword=keyword,
        tactical_context=args.get("tactical_context", {}) if isinstance(args.get("tactical_context"), dict) else {},
    )
