from __future__ import annotations

import json
import re
import ollama
from pathlib import Path

from infra.settings import OLLAMA_CHAT_MODEL
from v2.contracts import IngestResult, RequestFilter
from v2.metadata import MetadataProvider
from v2.tactician.persona_profile import build_persona_context

VALID_OPS = {"eq", "contains", "in", "range"}
_PROVIDER = MetadataProvider()
VALID_ENTITIES = set(_PROVIDER.get_all_tables())
_CHOICE_CACHE: dict[str, dict[str, str]] | None = None
_PARSER_STATS_PATH = Path("storage/v2/ingest/parser_stats_v2.json")


def _load_choice_cache() -> dict[str, dict[str, str]]:
    global _CHOICE_CACHE
    if _CHOICE_CACHE is not None:
        return _CHOICE_CACHE
    path = Path("db.json")
    out: dict[str, dict[str, str]] = {}
    if not path.exists():
        _CHOICE_CACHE = out
        return out
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _CHOICE_CACHE = out
        return out
    choice_options = raw.get("choice_options", {}) if isinstance(raw.get("choice_options"), dict) else {}
    for group, items in choice_options.items():
        if not isinstance(items, list):
            continue
        key = str(group).strip()
        if not key:
            continue
        lm: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            label = str(item.get("label", "")).strip()
            if code and label:
                lm[label.lower()] = code
        out[key] = lm
    _CHOICE_CACHE = out
    return out


def _choice_label_to_code(table: str, field: str, value: str) -> str | None:
    cache = _load_choice_cache()
    key = f"{table}.{field}"
    lm = cache.get(key, {})
    if not lm:
        return None
    v = str(value or "").strip().lower()
    if not v:
        return None
    return lm.get(v)


def _choice_value_grounded(table: str, field: str, value: str, lowered_query: str) -> bool:
    cache = _load_choice_cache()
    key = f"{table}.{field}"
    lm = cache.get(key, {})
    if not lm:
        return False
    val = str(value or "").strip()
    if not val:
        return False
    labels = [label for label, code in lm.items() if str(code) == val]
    return any(label in lowered_query for label in labels)


def _detect_tables_from_query(query: str) -> list[str]:
    lowered = str(query or "").lower()
    found: list[str] = []
    seen: set[str] = set()
    for alias, table in _PROVIDER.iter_alias_items():
        a = str(alias or "").strip().lower()
        t = str(table or "").strip()
        if not a or not t:
            continue
        if f" {a} " in f" {lowered} ":
            if t not in seen:
                seen.add(t)
                found.append(t)
    return found


def _extract_dynamic_business_filters(query: str, candidate_tables: list[str]) -> list[RequestFilter]:
    """
    Parse filters from generic patterns:
    - 'theo <field phrase> <value>'
    - 'by <field phrase> <value>'
    without hard-coding specific business fields/tables.
    """
    out: list[RequestFilter] = []
    used_keys: set[tuple[str, str, str]] = set()
    patterns = [
        r"(?:theo|by)\s+([a-zA-Z0-9_\-\s\u00C0-\u024F]+?)\s+([^\n\r,;]+)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, query, flags=re.IGNORECASE):
            field_phrase = str(m.group(1) or "").strip()
            value = str(m.group(2) or "").strip()
            value = re.split(r"\b(và|va|and|with|liên quan|lien quan)\b", value, maxsplit=1)[0].strip()
            if len(field_phrase) < 2 or len(value) < 1:
                continue
            normalized_field = field_phrase.replace(" ", "_").strip().lower()
            for table in candidate_tables:
                resolved = _PROVIDER.resolve_column_alias(table, normalized_field) or _PROVIDER.resolve_column_alias(
                    table, field_phrase
                )
                if not resolved:
                    continue
                mapped = _choice_label_to_code(table, resolved, value)
                final_value = mapped if mapped else value
                key = (table, resolved, str(final_value))
                if key in used_keys:
                    continue
                used_keys.add(key)
                out.append(RequestFilter(field=f"{table}.{resolved}", op="eq", value=final_value))
    return out


# ENTITY_ALIAS_MAP is now handled by _PROVIDER.get_table_by_alias


def _rule_based_detail_parse(query: str) -> tuple[str, list[str], list[RequestFilter], dict, float] | None:
    lowered = str(query or "").strip().lower()
    detail_markers = ["chi tiết", "chi tiet", "thông tin", "thong tin", "details", "detail", "lấy chi tiết", "lay chi tiet"]
    if not any(m in lowered for m in detail_markers):
        return None

    # Pattern: "<marker> ... <alias> <name>"
    for alias, table in _PROVIDER.iter_alias_items():
        if not alias or alias.startswith(("hbl_", "cr987_", "mc_")):
            continue
        pattern = rf"(?:chi tiết|chi tiet|thông tin|thong tin|details?|lấy chi tiết|lay chi tiet)\s+(?:về|ve|của|cua)?\s*{re.escape(alias)}\s+([^\n\r,;]{{2,100}})"
        m = re.search(pattern, query, re.IGNORECASE)
        if not m:
            continue
        name = str(m.group(1) or "").strip()
        if len(name) < 3:
            continue
        name = re.split(r"\b(và|va|cùng|cung|with|liên quan|lien quan|filter|lọc|loc)\b", name, maxsplit=1)[0].strip()
        name = re.sub(r"\b(là gì|la gi|là ai|la ai|is who|is what)\b.*$", "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r"\b(trong crm|trên crm|tren crm|in crm)\b.*$", "", name, flags=re.IGNORECASE).strip()
        if len(name) < 3:
            continue
        identity_field = _PROVIDER.resolve_identity_field(table) or "name"
        return (
            "retrieve",
            [table],
            [RequestFilter(field=f"{table}.{identity_field}", op=("contains" if len(name.split()) <= 2 else "eq"), value=name)],
            {},
            0.15,
        )
    return None


def _parse_simple_filters(query: str) -> list[RequestFilter]:
    filters: list[RequestFilter] = []
    lowered = query.lower()
    if "account" in lowered and "demo account" in lowered:
        m = re.search(r"(demo account\s*\d+)", lowered)
        if m:
            table = _PROVIDER.get_table_by_alias("account") or _PROVIDER.get_default_root_table()
            identity_field = _PROVIDER.resolve_identity_field(table) or "name"
            filters.append(RequestFilter(field=f"{table}.{identity_field}", op="contains", value=m.group(1)))

    candidate_tables = _detect_tables_from_query(query) or [_PROVIDER.get_default_root_table()]
    filters.extend(_extract_dynamic_business_filters(query, candidate_tables))
    return filters


def _detect_intent(query: str) -> str:
    lowered = query.lower()
    if any(x in lowered for x in ["thống kê", "bao cao", "báo cáo", "compare", "so với", "so voi", "đếm", "bao nhiêu"]):
        return "analyze"
    if any(x in lowered for x in ["cập nhật", "update", "chỉnh sửa", "sua", "sửa", "chốt"]):
        return "update"
    if any(x in lowered for x in ["create", "tạo", "them", "thêm"]):
        return "create"
    if any(x in lowered for x in ["chi tiet", "chi tiết", "thong tin", "thông tin", "list", "danh sach", "danh sách"]):
        return "retrieve"
    return "unknown"


def _detect_entities(query: str) -> list[str]:
    lowered = query.lower()
    entities: set[str] = set()
    # Simple strategy: scan for all known aliases in query
    for alias, table in _PROVIDER.iter_alias_items():
        if alias and f" {alias} " in f" {lowered} " or lowered.startswith(f"{alias} ") or lowered.endswith(f" {alias}"):
            entities.add(table)
    return sorted(entities)


def _extract_temporal_constraints(query: str) -> dict:
    lowered = str(query or "").lower()
    months = []
    for m in re.finditer(r"tháng\s*(\d{1,2})(?:[/-](\d{4})|\s*năm\s*(\d{4}))?", lowered, flags=re.IGNORECASE):
        month = int(m.group(1))
        year = m.group(2) or m.group(3)
        months.append({"month": month, "year": int(year) if year else None})
    return {
        "today": "hôm nay" in lowered or "hom nay" in lowered,
        "this_week": "tuần này" in lowered or "tuan nay" in lowered,
        "this_month": "tháng này" in lowered or "thang nay" in lowered,
        "month_refs": months,
        "compare": any(x in lowered for x in ["so với", "so voi", "compare"]),
    }


def _extract_work_intent(query: str) -> dict:
    lowered = str(query or "").lower()
    return {
        "needs_action": any(
            x in lowered
            for x in [
                "cần xử lý",
                "can xu ly",
                "cần làm",
                "can lam",
                "chăm sóc",
                "cham soc",
                "todo",
                "next action",
                "phải action",
                "phai action",
            ]
        ),
        "running_scope": any(x in lowered for x in ["đang chạy", "dang chay"]),
        "sort_by_action_date": any(x in lowered for x in ["sắp xếp", "sap xep", "sort"]) and any(
            x in lowered for x in ["ngày", "ngay", "action"]
        ),
    }


def _extract_owner_targets(query: str) -> list[dict]:
    lowered = str(query or "").lower()
    owners: list[dict] = []
    patterns = [
        r"(?:của|cua)\s+([A-Za-z0-9][A-Za-z0-9 _\-.]{2,80})",
        r"(?:tôi là|toi la)\s+([A-Za-z0-9][A-Za-z0-9 _\-.]{2,80})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, query, flags=re.IGNORECASE):
            raw = str(m.group(1) or "").strip()
            raw = re.split(r"\b(hôm nay|hom nay|tuần này|tuan nay|tháng này|thang nay|không|khong|\?)\b", raw, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if len(raw) < 3 or _looks_like_noise_target(raw):
                continue
            owners.append({"raw": raw, "normalized": raw.lower()})
    if "presales" in lowered:
        owners.append({"raw": "Presales", "normalized": "presales", "kind": "persona"})
    return owners


def _extract_identity_targets(query: str, entities: list[str]) -> list[dict]:
    targets: list[dict] = []
    for email in re.findall(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b", str(query or "")):
        targets.append({"kind": "email", "value": email})
    for url in re.findall(r"https?://[^\s]+", str(query or "")):
        targets.append({"kind": "url", "value": url})
    named_targets = _extract_named_targets(query)
    for table in entities:
        target = named_targets.get(table)
        if target:
            targets.append({"kind": "name", "table": table, "value": target})
    general = named_targets.get("__GENERAL__")
    if general:
        targets.append({"kind": "name", "value": general})
    return targets


def _build_intent_frame(query: str, intent: str, entities: list[str], filters: list[RequestFilter]) -> dict:
    temporal = _extract_temporal_constraints(query)
    work_intent = _extract_work_intent(query)
    owners = _extract_owner_targets(query)
    identity_targets = _extract_identity_targets(query, entities)
    has_identity = bool(identity_targets)
    filter_tables = {
        str(f.field).split(".", 1)[0]
        for f in filters
        if isinstance(f, RequestFilter) and "." in str(f.field)
    }
    reasoning_mode = "generic_retrieval"
    if intent == "analyze" or temporal.get("compare") or temporal.get("month_refs"):
        reasoning_mode = "aggregate_report"
    elif work_intent.get("needs_action") or work_intent.get("running_scope"):
        reasoning_mode = "compass_query"
    elif owners and entities:
        reasoning_mode = "scoped_retrieval"
    elif filters and (len(filter_tables) > 1 or (entities and any(t != entities[0] for t in filter_tables))):
        reasoning_mode = "scoped_retrieval"
    elif has_identity and entities:
        reasoning_mode = "identity_lookup"
    elif filters:
        reasoning_mode = "scoped_retrieval"
    return {
        "reasoning_mode": reasoning_mode,
        "temporal": temporal,
        "work_intent": work_intent,
        "owner_targets": owners,
        "identity_targets": identity_targets,
        "has_identity_targets": has_identity,
    }


def _is_generic_list_query(query: str) -> bool:
    lowered = query.lower()
    generic_tokens = ["danh sách", "danh sach", "list", "liệt kê", "liet ke"]
    return any(t in lowered for t in generic_tokens) and any(a in lowered for a in _PROVIDER.get_all_aliases())


def _looks_like_noise_target(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if len(text) < 2:
        return True
    blocked_exact = {
        "cac",
        "các",
        "nao",
        "nào",
        "tren crm dang co",
        "trên crm đang có",
        "trong crm",
        "trên crm",
        "dang co",
        "đang có",
    }
    if text in blocked_exact:
        return True
    blocked_prefixes = [
        "nao ",
        "nào ",
        "cac ",
        "các ",
        "tren crm ",
        "trên crm ",
        "trong crm ",
        "dang co ",
        "đang có ",
        "co ",
        "có ",
    ]
    if any(text.startswith(prefix) for prefix in blocked_prefixes):
        return True
    blocked_contains = [
        "can xu ly",
        "cần xử lý",
        "hom nay",
        "hôm nay",
        "tuan nay",
        "tuần này",
        "thang nay",
        "tháng này",
    ]
    return any(token in text for token in blocked_contains)


def _extract_named_targets(query: str) -> dict[str, str]:
    targets: dict[str, str] = {}
    lowered = query.lower()
    generic_list_mode = _is_generic_list_query(query)
    # 1. Broad scan: if "chi tiết <value>" is found, assume value is related to detected entity
    if "chi tiết" in lowered or "details" in lowered:
        cleaned = re.sub(r"\b(chi tiết|cho biết|xem|details|show|about|info)\b", "", lowered, flags=re.IGNORECASE).strip()
        # If we have exactly one entity, assign this cleaned string to its primary name field
        # But for now, we just pass it as a potential keyword
        if len(cleaned) >= 3:
            # We don't know the table yet, so we return a placeholder table or wait for _sanitize
            targets["__GENERAL__"] = cleaned

    for alias, table in _PROVIDER.iter_alias_items():
        if alias.startswith("hbl_") or alias.startswith("cr987_") or alias.startswith("mc_"):
            continue
        
        # Regex for "<alias> <value>"
        p1 = rf"{re.escape(alias)}\s+([^\n\r,;]{{2,80}})"
        m1 = re.search(p1, query, re.IGNORECASE)
        if m1:
            val = m1.group(1).strip()
            # Normalize copula prefix: "account là Demo Account 1" -> "Demo Account 1"
            val = re.sub(r"^(là|la|is|=)\s+", "", val, flags=re.IGNORECASE).strip()
            # Update-like queries often append payload after ":"; keep only entity name.
            val = val.split(":", 1)[0].strip()
            # Avoid picking up trailing list keywords or intent markers
            if not _is_generic_list_query(val):
                val = re.split(r"\b(và|va|cùng|cung|with|liên quan|lien quan|co|có|thuoc|thuộc)\b", val, maxsplit=1)[0].strip()
                if len(val) >= 3 and not _looks_like_noise_target(val):
                    targets[table] = val
        
        # Regex for "<value> <alias>" (e.g. "FPT contact")
        p2 = rf"([^\n\r,;]{{2,80}})\s+{re.escape(alias)}"
        m2 = re.search(p2, query, re.IGNORECASE)
        if m2:
            # Skip false positives like "Demo Account 1" where alias is part of value.
            tail = query[m2.end() :].strip()
            if tail and tail[0].isdigit():
                continue
            val = m2.group(1).strip()
            # Avoid picking up intent markers or list keywords
            val = re.sub(r"\b(chi tiết|xem|lấy|show|get|list|danh sách|danh sach|danh s|liệt kê|liet ke)\b", "", val, flags=re.IGNORECASE).strip()
            val = val.split(":", 1)[0].strip()
            if re.search(r"\b(lọc|loc|chỉ|chi|lấy|lay|danh sách|danh sach|list|show|get|xem)\b", val, flags=re.IGNORECASE):
                continue
            if generic_list_mode:
                continue
            if len(val) >= 3 and not _looks_like_noise_target(val):
                targets[table] = val

    return targets


def _sanitize_and_enrich_filters(query: str, entities: list[str], filters: list[RequestFilter]) -> list[RequestFilter]:
    lowered = query.lower()
    named_targets = _extract_named_targets(query)
    out: list[RequestFilter] = []
    entity_set = set(entities)
    for f in filters:
        field = str(f.field or "").strip()
        op = str(f.op or "").strip().lower()
        value = f.value
        if not field or op not in VALID_OPS:
            continue
        if "." in field:
            table, _col = field.split(".", 1)
        else:
            table = entities[0] if entities else _PROVIDER.get_default_root_table()
            field = f"{table}.{field}"
        if table not in VALID_ENTITIES:
            continue
        if entity_set and table not in entity_set:
            continue
        if op in {"eq", "contains"}:
            val = str(value or "").strip().lower()
            if len(val) < 2:
                continue
            # Value must be grounded in user query or extracted target.
            col = field.split(".", 1)[1] if "." in field else field
            grounded = (
                val in lowered
                or val == str(named_targets.get(table, "")).lower()
                or _choice_value_grounded(table, col, str(value or ""), lowered)
            )
            if not grounded:
                continue
        out.append(RequestFilter(field=field, op=op, value=value))

    # If no trusted filter but user named an entity value, derive exact condition.
    if not out:
        # Check __GENERAL__ first
        general_val = named_targets.get("__GENERAL__")
        if general_val and entities:
            table = entities[0]
            identity_field = _PROVIDER.resolve_identity_field(table) or "name"
            out.append(RequestFilter(field=f"{table}.{identity_field}", op="contains", value=general_val))
        else:
            for table in entities:
                target = named_targets.get(table)
                if target:
                    identity_field = _PROVIDER.resolve_identity_field(table) or "name"
                    out.append(RequestFilter(field=f"{table}.{identity_field}", op="eq", value=target))
                    break
    return _dedupe_filters(out)


def _dedupe_filters(out: list[RequestFilter]) -> list[RequestFilter]:
    # De-duplicate overlapping filters produced by mixed parser signals.
    # Example: keep "Demo Account 1", drop weaker duplicate like "Demo".
    deduped: list[RequestFilter] = []
    for f in out:
        if f.op != "eq" or not isinstance(f.value, str):
            deduped.append(f)
            continue
        current_val = str(f.value).strip()
        replaced = False
        for i, ex in enumerate(deduped):
            if ex.field == f.field and ex.op == "eq" and isinstance(ex.value, str):
                existing_val = str(ex.value).strip()
                if current_val.lower() == existing_val.lower():
                    replaced = True
                    break
                if current_val.lower() in existing_val.lower():
                    replaced = True
                    break
                if existing_val.lower() in current_val.lower():
                    deduped[i] = RequestFilter(field=f.field, op=f.op, value=current_val)
                    replaced = True
                    break
        if not replaced:
            deduped.append(f)
    # Remove weak partial values when a stronger exact value exists elsewhere.
    strong_values = [
        str(f.value).strip().lower()
        for f in deduped
        if f.op == "eq" and isinstance(f.value, str) and len(str(f.value).strip()) >= 6
    ]
    final_filters: list[RequestFilter] = []
    for f in deduped:
        if f.op == "eq" and isinstance(f.value, str):
            v = str(f.value).strip().lower()
            if len(v) <= 5 and any(v in sv and sv != v for sv in strong_values):
                continue
        final_filters.append(f)
    return final_filters


def _read_parser_stats() -> dict:
    if not _PARSER_STATS_PATH.exists():
        return {"runs": 0, "deterministic_applied_runs": 0, "deterministic_rate": 0.0}
    try:
        raw = json.loads(_PARSER_STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"runs": 0, "deterministic_applied_runs": 0, "deterministic_rate": 0.0}
    if not isinstance(raw, dict):
        return {"runs": 0, "deterministic_applied_runs": 0, "deterministic_rate": 0.0}
    return raw


def _update_parser_stats(deterministic_applied: bool) -> dict:
    stats = _read_parser_stats()
    runs = int(stats.get("runs", 0) or 0) + 1
    det = int(stats.get("deterministic_applied_runs", 0) or 0) + (1 if deterministic_applied else 0)
    rate = round((det / runs), 4) if runs > 0 else 0.0
    out = {
        "runs": runs,
        "deterministic_applied_runs": det,
        "deterministic_rate": rate,
        "warning_threshold": 0.2,
        "warning": rate > 0.2,
    }
    _PARSER_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PARSER_STATS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _llm_parse(query: str) -> tuple[str, list[str], list[RequestFilter], dict, float]:
    valid_tables = list(_PROVIDER.get_all_tables())
    prompt = """
You are a CRM request parser.
Return strict JSON with this schema:
{{
  "intent": "retrieve|analyze|create|update|unknown",
  "entity_types": {valid_tables},
  "filters": [{{"field":"table.field","op":"eq|contains|in|range","value":"..."}}],
  "update_data": {{"field_name": "value"}},
  "ambiguity_score": 0.0
}}
Note: For filters, use primary name fields like 'hbl_contact_name' or 'hbl_account_name' unless specific fields are implied.

Rules:
- If intent is 'update', extract BANT (Budget, Authority, Need, Timeline) into 'update_data'.
- Map BANT to these logic keys: 'budget' (amount), 'authority' (role), 'need' (description), 'timeline' (date/quarter).
- If user asks generic list like "danh sach account", keep filters empty.
- Only add filters when user gives specific identity/condition.
- Keep ambiguity_score high (>=0.7) when requirement is unclear.

User query: {query}
""".strip()
    prompt = (
        prompt.replace("{valid_tables}", json.dumps(valid_tables)).replace("{query}", query)
    )
    response = ollama.generate(model=OLLAMA_CHAT_MODEL, prompt=prompt, format="json")
    raw = json.loads(response["response"])
    intent = str(raw.get("intent", "unknown")).strip().lower()
    if intent not in {"retrieve", "analyze", "create", "update", "unknown"}:
        intent = "unknown"
    
    update_data = raw.get("update_data", {}) if isinstance(raw.get("update_data"), dict) else {}
    entity_types = raw.get("entity_types", [])
    entities = sorted(
        {
            str(x).strip()
            for x in entity_types
            if str(x).strip() in VALID_ENTITIES
        }
    )
    filters: list[RequestFilter] = []
    for f in raw.get("filters", []) or []:
        if not isinstance(f, dict):
            continue
        field = str(f.get("field", "")).strip()
        op = str(f.get("op", "")).strip().lower()
        if not field or op not in VALID_OPS:
            continue
        filters.append(RequestFilter(field=field, op=op, value=f.get("value")))
    try:
        ambiguity = float(raw.get("ambiguity_score", 0.5))
    except (TypeError, ValueError):
        ambiguity = 0.5
    ambiguity = max(0.0, min(1.0, ambiguity))
    if _is_generic_list_query(query):
        filters = []
        ambiguity = min(ambiguity, 0.35)
    filters = _sanitize_and_enrich_filters(query, entities, filters)
    if entities and not filters and not _is_generic_list_query(query) and intent != "update":
        ambiguity = max(ambiguity, 0.7)
    return intent, entities, filters, update_data, ambiguity


def _apply_deterministic_overrides(
    query: str,
    intent: str,
    entities: list[str],
    filters: list[RequestFilter],
    ambiguity: float,
) -> tuple[str, list[str], list[RequestFilter], float, dict]:
    lowered = query.lower()
    named_targets = _extract_named_targets(query)
    entity_set = set(entities)
    new_filters = list(filters)
    aggregate_phrase_markers = ["thống kê", "thong ke", "bao cao", "báo cáo", "số lượng", "so luong", "doanh thu", "revenue"]
    aggregate_word_markers = ["count", "sum"]
    is_aggregate_like = any(x in lowered for x in aggregate_phrase_markers) or any(
        re.search(rf"\b{re.escape(x)}\b", lowered) for x in aggregate_word_markers
    )

    candidate_tables = _detect_tables_from_query(query) or (entities if entities else [_PROVIDER.get_default_root_table()])
    dynamic_business_filters = _extract_dynamic_business_filters(query, candidate_tables)
    dynamic_applied = False
    has_existing_filters = bool(new_filters)
    low_signal_mode = not has_existing_filters
    if dynamic_business_filters and low_signal_mode:
        for bf in dynamic_business_filters:
            field = str(bf.field)
            table = field.split(".", 1)[0] if "." in field else (entities[0] if entities else _PROVIDER.get_default_root_table())
            identity_field = _PROVIDER.resolve_identity_field(table) or "name"
            # When an explicit business filter exists (market/status/owner/...),
            # drop identity fallback filters for this table to avoid contradictions.
            new_filters = [
                f
                for f in new_filters
                if not (str(f.field) == f"{table}.{identity_field}" and str(f.op).lower() in {"eq", "contains"})
            ]
            new_filters.append(bf)
            entity_set.add(table)
            dynamic_applied = True
        if intent == "unknown":
            intent = "retrieve"
        ambiguity = min(ambiguity, 0.4)

    # If user provides explicit object identity (e.g. Demo Account 8),
    # this is a high-signal request and should not be blocked by clarify.
    named_applied = False
    if named_targets and low_signal_mode:
        fallback_entity = entities[0] if entities else _PROVIDER.get_default_root_table()
        for table, target in named_targets.items():
            target_table = table if table in VALID_ENTITIES else fallback_entity
            entity_set.add(target_table)
            if not any(str(f.field).startswith(f"{target_table}.") for f in new_filters):
                identity_field = _PROVIDER.resolve_identity_field(target_table) or "name"
                new_filters.append(RequestFilter(field=f"{target_table}.{identity_field}", op="eq", value=target))
                named_applied = True
        if intent == "unknown":
            intent = "retrieve"
        ambiguity = min(ambiguity, 0.45)

    # Explicit "thong tin/chi tiet" with known entity implies direct retrieval.
    if any(x in lowered for x in ["thong tin", "thông tin", "chi tiet", "chi tiết"]) and entity_set:
        if intent == "unknown":
            intent = "retrieve"
        ambiguity = min(ambiguity, 0.35)

    # Aggregate/report requests should not be forced into name filters.
    aggregate_override_applied = False
    if is_aggregate_like:
        if intent != "update":
            intent = "analyze"
        new_filters = []
        ambiguity = min(ambiguity, 0.25)
        aggregate_override_applied = True

    diagnostics = {
        "low_signal_mode": low_signal_mode,
        "dynamic_business_filters_detected": len(dynamic_business_filters),
        "dynamic_override_applied": dynamic_applied,
        "named_targets_detected": len(named_targets),
        "named_override_applied": named_applied,
        "aggregate_override_applied": aggregate_override_applied,
        "deterministic_applied": bool(dynamic_applied or named_applied or aggregate_override_applied),
    }
    return intent, sorted(entity_set), new_filters, ambiguity, diagnostics


def ingest_query(query: str, role: str = "DEFAULT") -> IngestResult:
    normalized = re.sub(r"\s+", " ", str(query or "").strip())
    update_data = {}
    persona_context = build_persona_context(role=role)
    rule_based = _rule_based_detail_parse(normalized)
    if rule_based:
        intent, entities, request_filters, update_data, ambiguity_score = rule_based
        request_filters = _dedupe_filters(request_filters)
        intent_frame = _build_intent_frame(normalized, intent, entities, request_filters)
        persona_context = dict(persona_context)
        persona_context["intent_frame"] = intent_frame
        return IngestResult(
            raw_query=query,
            normalized_query=normalized,
            intent=intent,
            entities=entities,
            request_filters=request_filters,
            update_data=update_data,
            ambiguity_score=ambiguity_score,
            role=role,
            domain="general",
            persona_context=persona_context,
        )

    # Fast-path parser (PRD/UX: core runtime must be responsive).
    # Only fall back to LLM parsing when the query is genuinely low-signal.
    intent = _detect_intent(normalized)
    entities = _detect_entities(normalized)
    request_filters = _parse_simple_filters(normalized)
    if _is_generic_list_query(normalized):
        ambiguity_score = 0.25 if entities else 0.35
    elif entities or request_filters or intent != "unknown":
        # High-signal deterministic parse: keep latency low, then allow
        # downstream agentic reasoner + trust gate to handle edge conditions.
        ambiguity_score = 0.35 if (entities and not request_filters and intent != "update") else 0.15
    else:
        # Low-signal: allow LLM to infer intent/entities/filters.
        try:
            intent, entities, request_filters, update_data, ambiguity_score = _llm_parse(normalized)
        except Exception:
            ambiguity_score = 0.85

    intent, entities, request_filters, ambiguity_score, parser_diag = _apply_deterministic_overrides(
        normalized, intent, entities, request_filters, ambiguity_score
    )
    request_filters = _dedupe_filters(request_filters)
    intent_frame = _build_intent_frame(normalized, intent, entities, request_filters)
    if intent_frame.get("reasoning_mode") in {"compass_query", "identity_lookup", "scoped_retrieval"} and not request_filters:
        ambiguity_score = max(float(ambiguity_score), 0.55)
    if intent_frame.get("reasoning_mode") == "compass_query" and not entities:
        ambiguity_score = max(float(ambiguity_score), 0.75)
    parser_stats = _update_parser_stats(bool(parser_diag.get("deterministic_applied", False)))
    persona_context = dict(persona_context)
    persona_context["parser_diagnostics"] = parser_diag
    persona_context["parser_stats"] = parser_stats
    persona_context["intent_frame"] = intent_frame
    return IngestResult(
        raw_query=query,
        normalized_query=normalized,
        intent=intent,
        entities=entities,
        request_filters=request_filters,
        update_data=update_data,
        ambiguity_score=ambiguity_score,
        role=role,
        domain="general",
        persona_context=persona_context,
    )
