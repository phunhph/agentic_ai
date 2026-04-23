from __future__ import annotations

import json
import re
import ollama

from infra.settings import OLLAMA_CHAT_MODEL
from v2.contracts import IngestResult, RequestFilter
from v2.metadata import load_v2_metadata

VALID_OPS = {"eq", "contains", "in", "range"}
_METADATA = load_v2_metadata()
VALID_ENTITIES = set(_METADATA.tables)


def _entity_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for table in VALID_ENTITIES:
        alias_map[table] = table
        compact = table.replace("hbl_", "").replace("cr987_", "").replace("_", " ").strip()
        if compact:
            alias_map[compact] = table
            if compact.endswith("ies"):
                alias_map[compact[:-3] + "y"] = table
            elif compact.endswith("s"):
                alias_map[compact[:-1]] = table
            else:
                alias_map[compact + "s"] = table
    return alias_map


ENTITY_ALIAS_MAP = _entity_alias_map()


def _parse_simple_filters(query: str) -> list[RequestFilter]:
    filters: list[RequestFilter] = []
    lowered = query.lower()
    if "account" in lowered and "demo account" in lowered:
        m = re.search(r"(demo account\s*\d+)", lowered)
        if m:
            filters.append(RequestFilter(field="hbl_account.name", op="contains", value=m.group(1)))
    return filters


def _detect_intent(query: str) -> str:
    lowered = query.lower()
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
    for alias, table in ENTITY_ALIAS_MAP.items():
        if alias and alias in lowered:
            entities.add(table)
    if "opp" in lowered and "hbl_opportunities" in VALID_ENTITIES:
        entities.add("hbl_opportunities")
    return sorted(entities)


def _is_generic_list_query(query: str) -> bool:
    lowered = query.lower()
    generic_tokens = ["danh sách", "danh sach", "list", "liệt kê", "liet ke"]
    return any(t in lowered for t in generic_tokens) and any(a in lowered for a in ENTITY_ALIAS_MAP.keys())


def _extract_named_targets(query: str) -> dict[str, str]:
    targets: dict[str, str] = {}
    # Generic, metadata-driven target extraction: "<entity alias> <value...>"
    # without table-specific hard coding.
    for alias, table in ENTITY_ALIAS_MAP.items():
        if alias.startswith("hbl_"):
            continue
        p = rf"{re.escape(alias)}\s+([A-Za-z0-9][A-Za-z0-9 _\-.]{{2,80}})"
        m = re.search(p, query, re.IGNORECASE)
        if not m:
            continue
        val = m.group(1).strip()
        val = re.split(r"\b(và|va|cùng|cung|with|liên quan|lien quan|co|có|thuoc|thuộc)\b", val, maxsplit=1)[0].strip()
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
            table = entities[0] if entities else "hbl_account"
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
        for table in entities:
            target = named_targets.get(table)
            if target:
                out.append(RequestFilter(field=f"{table}.name", op="eq", value=target))
                break
    return out


def _llm_parse(query: str) -> tuple[str, list[str], list[RequestFilter], float]:
    prompt = f"""
You are a CRM request parser.
Return strict JSON with this schema:
{{
  "intent": "retrieve|analyze|create|unknown",
  "entity_types": ["hbl_account","hbl_contact","hbl_contract","hbl_opportunities"],
  "filters": [{{"field":"table.field","op":"eq|contains|in|range","value":"..."}}],
  "ambiguity_score": 0.0
}}

Rules:
- If user asks generic list like "danh sach account", keep filters empty.
- Only add filters when user gives specific identity/condition.
- Keep ambiguity_score high (>=0.7) when requirement is unclear.

User query: {query}
""".strip()
    response = ollama.generate(model=OLLAMA_CHAT_MODEL, prompt=prompt, format="json")
    raw = json.loads(response["response"])
    intent = str(raw.get("intent", "unknown")).strip().lower()
    if intent not in {"retrieve", "analyze", "create", "unknown"}:
        intent = "unknown"
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
    if entities and not filters and not _is_generic_list_query(query):
        ambiguity = max(ambiguity, 0.7)
    return intent, entities, filters, ambiguity


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
        for table, target in named_targets.items():
            entity_set.add(table)
            if not any(str(f.field).startswith(f"{table}.") for f in new_filters):
                new_filters.append(RequestFilter(field=f"{table}.name", op="eq", value=target))
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
    try:
        intent, entities, request_filters, ambiguity_score = _llm_parse(normalized)
    except Exception:
        intent = _detect_intent(normalized)
        entities = _detect_entities(normalized)
        request_filters = _parse_simple_filters(normalized)
        ambiguity_score = 0.75 if intent == "unknown" or not entities else 0.15

    intent, entities, request_filters, ambiguity_score = _apply_deterministic_overrides(
        normalized, intent, entities, request_filters, ambiguity_score
    )
    return IngestResult(
        raw_query=query,
        normalized_query=normalized,
        intent=intent,
        entities=entities,
        request_filters=request_filters,
        ambiguity_score=ambiguity_score,
        role=role,
        domain="general",
    )
