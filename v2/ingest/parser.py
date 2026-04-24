from __future__ import annotations

import json
import re
import ollama

from infra.settings import OLLAMA_CHAT_MODEL
from v2.contracts import IngestResult, RequestFilter
from v2.metadata import MetadataProvider
from v2.tactician.persona_profile import build_persona_context

VALID_OPS = {"eq", "contains", "in", "range"}
_PROVIDER = MetadataProvider()
VALID_ENTITIES = set(_PROVIDER.get_all_tables())


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
        pattern = rf"(?:chi tiết|chi tiet|thông tin|thong tin|details?|lấy chi tiết|lay chi tiet)\s+(?:về|ve|của|cua)?\s*{re.escape(alias)}\s+([A-Za-z0-9][A-Za-z0-9 _\-.]{{2,100}})"
        m = re.search(pattern, query, re.IGNORECASE)
        if not m:
            continue
        name = str(m.group(1) or "").strip()
        if len(name) < 3:
            continue
        name = re.split(r"\b(và|va|cùng|cung|with|liên quan|lien quan|filter|lọc|loc)\b", name, maxsplit=1)[0].strip()
        if len(name) < 3:
            continue
        identity_field = _PROVIDER.resolve_identity_field(table) or "name"
        return (
            "retrieve",
            [table],
            [RequestFilter(field=f"{table}.{identity_field}", op="eq", value=name)],
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
    return filters


def _detect_intent(query: str) -> str:
    lowered = query.lower()
    if any(x in lowered for x in ["cập nhật", "update", "chỉnh sửa", "sua", "sửa", "chốt"]):
        return "update"
    if any(x in lowered for x in ["create", "tạo", "them", "thêm"]):
        return "create"
    if any(x in lowered for x in ["thống kê", "bao cao", "báo cáo", "compare"]):
        return "analyze"
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


def _is_generic_list_query(query: str) -> bool:
    lowered = query.lower()
    generic_tokens = ["danh sách", "danh sach", "list", "liệt kê", "liet ke"]
    return any(t in lowered for t in generic_tokens) and any(a in lowered for a in _PROVIDER.get_all_aliases())


def _extract_named_targets(query: str) -> dict[str, str]:
    targets: dict[str, str] = {}
    lowered = query.lower()
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
        p1 = rf"{re.escape(alias)}\s+([A-Za-z0-9][A-Za-z0-9 _\-.]{{2,80}})"
        m1 = re.search(p1, query, re.IGNORECASE)
        if m1:
            val = m1.group(1).strip()
            # Avoid picking up trailing list keywords or intent markers
            if not _is_generic_list_query(val):
                val = re.split(r"\b(và|va|cùng|cung|with|liên quan|lien quan|co|có|thuoc|thuộc)\b", val, maxsplit=1)[0].strip()
                if len(val) >= 3:
                    targets[table] = val
        
        # Regex for "<value> <alias>" (e.g. "FPT contact")
        p2 = rf"([A-Za-z0-9][A-Za-z0-9 _\-.]{{2,80}})\s+{re.escape(alias)}"
        m2 = re.search(p2, query, re.IGNORECASE)
        if m2:
            val = m2.group(1).strip()
            # Avoid picking up intent markers or list keywords
            val = re.sub(r"\b(chi tiết|xem|lấy|show|get|list|danh sách|danh sach|danh s|liệt kê|liet ke)\b", "", val, flags=re.IGNORECASE).strip()
            if len(val) >= 3:
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
            grounded = val in lowered or val == str(named_targets.get(table, "")).lower()
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
) -> tuple[str, list[str], list[RequestFilter], float]:
    lowered = query.lower()
    named_targets = _extract_named_targets(query)
    entity_set = set(entities)
    new_filters = list(filters)

    # If user provides explicit object identity (e.g. Demo Account 8),
    # this is a high-signal request and should not be blocked by clarify.
    if named_targets:
        fallback_entity = entities[0] if entities else _PROVIDER.get_default_root_table()
        for table, target in named_targets.items():
            target_table = table if table in VALID_ENTITIES else fallback_entity
            entity_set.add(target_table)
            if not any(str(f.field).startswith(f"{target_table}.") for f in new_filters):
                identity_field = _PROVIDER.resolve_identity_field(target_table) or "name"
                new_filters.append(RequestFilter(field=f"{target_table}.{identity_field}", op="eq", value=target))
        if intent == "unknown":
            intent = "retrieve"
        ambiguity = min(ambiguity, 0.25)

    # Explicit "thong tin/chi tiet" with known entity implies direct retrieval.
    if any(x in lowered for x in ["thong tin", "thông tin", "chi tiet", "chi tiết"]) and entity_set:
        if intent == "unknown":
            intent = "retrieve"
        ambiguity = min(ambiguity, 0.35)

    return intent, sorted(entity_set), new_filters, ambiguity


def ingest_query(query: str, role: str = "DEFAULT") -> IngestResult:
    normalized = re.sub(r"\s+", " ", str(query or "").strip())
    update_data = {}
    persona_context = build_persona_context(role=role)
    rule_based = _rule_based_detail_parse(normalized)
    if rule_based:
        intent, entities, request_filters, update_data, ambiguity_score = rule_based
        request_filters = _dedupe_filters(request_filters)
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
    try:
        intent, entities, request_filters, update_data, ambiguity_score = _llm_parse(normalized)
    except Exception:
        intent = _detect_intent(normalized)
        entities = _detect_entities(normalized)
        request_filters = _parse_simple_filters(normalized)
        ambiguity_score = 0.75 if intent == "unknown" or not entities else 0.15

    intent, entities, request_filters, ambiguity_score = _apply_deterministic_overrides(
        normalized, intent, entities, request_filters, ambiguity_score
    )
    request_filters = _dedupe_filters(request_filters)
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
