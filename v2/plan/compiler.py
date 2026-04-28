import calendar
import re
from datetime import UTC, datetime

from v2.contracts import ExecutionPlan, IngestResult, RequestFilter
from v2.metadata import MetadataProvider

_PROVIDER = MetadataProvider()


def _pick_best_identity_field(table_name: str, keyword: str, intent_frame: dict | None = None) -> str | None:
    fields = _PROVIDER.get_identity_priority_fields(table_name)
    if not fields:
        return _PROVIDER.resolve_identity_field(table_name)
    text = str(keyword or "").strip()
    if table_name == "systemuser":
        if "@" in text:
            for field in ["domainname", "internalemailaddress"]:
                if field in fields:
                    return field
        return "fullname" if "fullname" in fields else fields[0]
    return fields[0]


def _build_identity_lookup_filters(root_table: str, keyword: str, intent_frame: dict | None = None) -> list[RequestFilter]:
    text = str(keyword or "").strip()
    if not text:
        return []
    field = _pick_best_identity_field(root_table, text, intent_frame=intent_frame)
    if not field:
        return []
    op = "eq"
    if root_table != "systemuser" and len(text.split()) <= 2 and "@" not in text:
        op = "contains"
    return [RequestFilter(field=f"{root_table}.{field}", op=op, value=text)]


def _build_compass_filters(root_table: str, intent_frame: dict | None = None) -> tuple[list[RequestFilter], list[str], list[str]]:
    frame = intent_frame if isinstance(intent_frame, dict) else {}
    temporal = frame.get("temporal", {}) if isinstance(frame.get("temporal"), dict) else {}
    filters: list[RequestFilter] = []
    include_tables: list[str] = []
    warnings: list[str] = []

    if temporal.get("today"):
        if root_table == "hbl_contact" and "hbl_contact_next_action_date" in _PROVIDER.get_fields("hbl_contact"):
            filters.append(
                RequestFilter(
                    field="hbl_contact.hbl_contact_next_action_date",
                    op="range",
                    value={"min": f"{datetime.now(UTC).date().isoformat()}T00:00:00", "max": f"{datetime.now(UTC).date().isoformat()}T23:59:59"},
                )
            )
        elif root_table == "hbl_opportunities" and "hbl_opportunitiest_next_time_action" in _PROVIDER.get_fields("hbl_opportunities"):
            filters.append(
                RequestFilter(
                    field="hbl_opportunities.hbl_opportunitiest_next_time_action",
                    op="range",
                    value={"min": f"{datetime.now(UTC).date().isoformat()}T00:00:00", "max": f"{datetime.now(UTC).date().isoformat()}T23:59:59"},
                )
            )
        elif root_table == "hbl_contract" and "hbl_contract_action_date" in _PROVIDER.get_fields("hbl_contract"):
            filters.append(
                RequestFilter(
                    field="hbl_contract.hbl_contract_action_date",
                    op="range",
                    value={"min": f"{datetime.now(UTC).date().isoformat()}T00:00:00", "max": f"{datetime.now(UTC).date().isoformat()}T23:59:59"},
                )
            )
        elif root_table == "hbl_account":
            if "hbl_contact" in _PROVIDER.get_all_tables():
                include_tables.append("hbl_contact")
                filters.append(
                    RequestFilter(
                        field="hbl_contact.hbl_contact_next_action_date",
                        op="range",
                        value={"min": f"{datetime.now(UTC).date().isoformat()}T00:00:00", "max": f"{datetime.now(UTC).date().isoformat()}T23:59:59"},
                    )
                )
            else:
                warnings.append("unsupported_compass_signal")
    if temporal.get("this_week") and root_table == "hbl_contact" and "hbl_contact_next_action_date" in _PROVIDER.get_fields("hbl_contact"):
        start = datetime.now(UTC).date()
        end = start.fromordinal(start.toordinal() + 6)
        filters.append(
            RequestFilter(
                field="hbl_contact.hbl_contact_next_action_date",
                op="range",
                value={"min": f"{start.isoformat()}T00:00:00", "max": f"{end.isoformat()}T23:59:59"},
            )
        )
    if not filters:
        warnings.append("unsupported_compass_signal")
    return filters, include_tables, warnings
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


def _pick_created_field(table_name: str) -> str | None:
    fields = _PROVIDER.get_fields(table_name)
    if not fields:
        return None
    exact_priorities = [
        "createdon",
        "create_on_origin",
        "create_on",
        "created_at",
        "created_date",
    ]
    fuzzy_priorities = [
        "created",
    ]
    lowered_map = {str(f).lower(): str(f) for f in fields}
    for token in exact_priorities:
        if token in lowered_map:
            return lowered_map[token]
    for token in fuzzy_priorities:
        for lf, orig in lowered_map.items():
            if token in lf:
                return orig
    return None


def _extract_month_year_pairs(text: str) -> list[tuple[int, int]]:
    matches = list(
        re.finditer(
            r"tháng\s*(\d{1,2})(?:\s*[,/-]?\s*(?:năm)?\s*(\d{4}))?",
            text,
            flags=re.IGNORECASE,
        )
    )
    if not matches:
        return []
    explicit_years = [int(m.group(2)) for m in matches if m.group(2)]
    fallback_year = explicit_years[-1] if explicit_years else datetime.now(UTC).year
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for m in matches:
        month = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else fallback_year
        if month < 1 or month > 12:
            continue
        pair = (year, month)
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    return pairs


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
    month_year_pairs = _extract_month_year_pairs(text)
    if not wants_count and not wants_revenue:
        wants_count = True

    if wants_count:
        for table in sorted(set(entities)):
            clean = table.replace("hbl_", "")
            created_field = _pick_created_field(table)
            if month_year_pairs and created_field:
                for year, month in month_year_pairs:
                    last_day = calendar.monthrange(year, month)[1]
                    ops.append(
                        {
                            "type": "count",
                            "table": table,
                            "alias": f"{clean}_count_{year}_{month:02d}",
                            "filters": [
                                {
                                    "field": f"{table}.{created_field}",
                                    "op": "range",
                                    "value": {
                                        "min": f"{year:04d}-{month:02d}-01T00:00:00",
                                        "max": f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59",
                                    },
                                }
                            ],
                        }
                    )
            else:
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
    reasoning_mode = str(args.get("reasoning_mode", "")).strip()
    intent_frame = args.get("intent_frame", {}) if isinstance(args.get("intent_frame"), dict) else {}

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
    elif reasoning_mode == "identity_lookup":
        where_filters = _build_identity_lookup_filters(root_table, keyword, intent_frame=intent_frame) or where_filters
    elif reasoning_mode == "compass_query":
        compass_filters, compass_include, _warnings = _build_compass_filters(root_table, intent_frame=intent_frame)
        if compass_filters:
            where_filters = compass_filters
            for table in compass_include:
                if table not in include_tables:
                    include_tables.append(table)
            keyword = ""
        else:
            keyword = ""
            where_filters = []
    elif keyword and not where_filters:
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
