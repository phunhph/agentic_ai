import re

from agent.field_resolver import INTENT_TOOL_HINT, resolve_request
from dynamic_metadata.case_memory import match_case
from dynamic_metadata.entity_extract import extract_entities
from dynamic_metadata.intent_llm import (
    extract_order_contract_id,
    llm_parse_intent_entities,
)
from dynamic_metadata.text_normalize import clean_goal_text, normalize_goal_text
from dynamic_metadata.tool_inference import infer_best_tool_for_tables
from dynamic_metadata.trace_metrics import estimate_tokens
from infra.settings import (
    PERCEPTION_COMPARE_VERBS,
    PERCEPTION_CREATE_VERBS,
    PERCEPTION_GENERIC_LIST_KEYWORDS,
)


_ACCOUNT_NAME_PATTERNS = [
    re.compile(r"\b(?:account|acocunt|accout|acount)\s*(?:la|là|=|is)?\s*([a-z0-9][a-z0-9\s\-_]{1,80})$", re.IGNORECASE),
    re.compile(r"\b(?:cua|của)\s*(?:account|acocunt|accout|acount)\s*([a-z0-9][a-z0-9\s\-_]{1,80})$", re.IGNORECASE),
]
_CREATE_VERBS = tuple(PERCEPTION_CREATE_VERBS)
_COMPARE_VERBS = tuple(PERCEPTION_COMPARE_VERBS)
_DETAIL_HINTS = ("chi tiet", "chi tiết", "thong tin", "thông tin", "detail")
_ENTITY_STOP_MARKERS = (
    " cung voi ",
    " cùng với ",
    " lien quan ",
    " liên quan ",
    " va ",
    " và ",
    " voi ",
    " với ",
    " customer ",
    " opp ",
    " opportunity ",
    " opportunities ",
    " contract ",
    " contact ",
    " account ",
)


def _extract_named_phrase_after(normalized_goal: str, token: str) -> str:
    marker = f" {token} "
    text = f" {normalized_goal} "
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[-1]
    tail = re.sub(r"^(la|là|is|=)\s+", "", tail).strip()
    if not tail:
        return ""
    cut = len(tail)
    padded_tail = f" {tail} "
    for stop in _ENTITY_STOP_MARKERS:
        idx = padded_tail.find(stop)
        if idx > 0:
            cut = min(cut, max(0, idx - 1))
    cleaned = tail[:cut].strip(" ,.;:-_")
    return " ".join(cleaned.split())


def _extract_customer_name_from_account_phrase(normalized_goal: str) -> str:
    m = re.search(
        r"\b(?:account|acocunt|acount|accout)\s+(.*?)(?:\s+(?:cung voi|cùng với|lien quan|liên quan|va|và|voi|với)\b|$)",
        normalized_goal,
        re.IGNORECASE,
    )
    if m:
        candidate = re.sub(r"^(la|là|is|=)\s+", "", m.group(1)).strip(" ,.;:-_")
        if candidate:
            return " ".join(candidate.split())
    for alias in ("account", "acocunt", "acount", "accout"):
        guessed = _extract_named_phrase_after(normalized_goal, alias)
        if guessed:
            return guessed
    for p in _ACCOUNT_NAME_PATTERNS:
        m = p.search(normalized_goal)
        if m:
            return m.group(1).strip()
    marker = None
    for candidate in (" account ", " acocunt ", " acount ", " accout "):
        if candidate in f" {normalized_goal} ":
            marker = candidate.strip()
            break
    if not marker:
        return ""
    return _extract_named_phrase_after(normalized_goal, marker)


def _fast_path_intent_entities(normalized_goal: str) -> tuple[str, dict] | None:
    """Rule-based fast path for common CRM commands to reduce LLM latency and intent drift."""
    has_contact = "contact" in normalized_goal
    has_contract = "contract" in normalized_goal
    has_opportunity = any(t in normalized_goal for t in ("opportunity", "opportunities", "ops", "cơ hội", "co hoi"))
    has_account = any(t in normalized_goal for t in ("account", "accounts", "acocunt", "acount", "accout"))
    is_create = any(v in normalized_goal for v in _CREATE_VERBS)
    is_compare = any(v in normalized_goal for v in _COMPARE_VERBS)
    is_detail = any(v in normalized_goal for v in _DETAIL_HINTS)
    wants_all_scope = any(v in normalized_goal for v in ("toan bo", "toàn bộ", "tong hop", "tổng hợp", "lien quan", "liên quan", "cung voi", "cùng với"))
    table_hits = [
        ("hbl_account", has_account),
        ("hbl_contact", has_contact),
        ("hbl_contract", has_contract),
        ("hbl_opportunities", has_opportunity),
    ]
    mentioned = [name for name, ok in table_hits if ok]

    if len(mentioned) >= 2 and wants_all_scope:
        root_table = "hbl_account" if has_account else mentioned[0]
        include_tables = [t for t in mentioned if t != root_table]
        keyword = _extract_customer_name_from_account_phrase(normalized_goal) if has_account else ""
        if not keyword:
            keyword = normalized_goal
        return "DYNAMIC_QUERY", {
            "root_table": root_table,
            "include_tables": include_tables,
            "keyword": keyword,
            "limit": 20,
        }

    if has_account and is_detail and wants_all_scope and (has_contact or has_contract or has_opportunity):
        keyword = _extract_customer_name_from_account_phrase(normalized_goal)
        if not keyword:
            keyword = normalized_goal
            for token in ("toan bo", "toàn bộ", "thong tin", "thông tin", "ve", "về", "account", "accoutn", "accout", "acocunt", "lien quan", "liên quan", "cung voi", "cùng với"):
                keyword = re.sub(rf"\b{re.escape(token)}\b", " ", keyword)
            keyword = " ".join(keyword.split()).strip()
        return "ACCOUNT_360", {"keyword": keyword} if keyword else {}

    if has_contact and is_detail:
        keyword = _extract_named_phrase_after(normalized_goal, "contact")
        if not keyword:
            keyword = normalized_goal
            for token in ("chi tiet", "chi tiết", "thong tin", "thông tin", "cua", "của", "contact"):
                keyword = re.sub(rf"\b{re.escape(token)}\b", " ", keyword)
            keyword = " ".join(keyword.split()).strip()
        return "CONTACT_DETAILS", {"keyword": keyword} if keyword else {}
    if has_contract and is_detail:
        keyword = _extract_named_phrase_after(normalized_goal, "contract")
        if not keyword:
            keyword = normalized_goal
            for token in ("chi tiet", "chi tiết", "thong tin", "thông tin", "cua", "của", "contract"):
                keyword = re.sub(rf"\b{re.escape(token)}\b", " ", keyword)
            keyword = " ".join(keyword.split()).strip()
        entities = {"keyword": keyword} if keyword else {}
        contract_id_match = re.search(r"\b(?:cr\d+|[0-9a-f]{8}-[0-9a-f-]{27})\b", normalized_goal, re.IGNORECASE)
        if contract_id_match:
            entities["contract_id"] = contract_id_match.group(0)
        return "CONTRACT_DETAILS", entities
    if has_contact and is_create:
        return "CONTACT_CREATE", {}
    if has_contact and is_compare:
        return "CONTACT_COMPARE", {}
    if has_contract and is_create:
        return "CONTRACT_CREATE", {}
    if has_contract and is_compare:
        return "CONTRACT_COMPARE", {}
    if has_opportunity and is_create:
        return "OPPORTUNITY_CREATE", {}
    if has_opportunity and is_compare:
        return "OPPORTUNITY_COMPARE", {}
    if has_account and is_create:
        return "ACCOUNT_CREATE", {}
    if has_account and is_compare:
        return "ACCOUNT_COMPARE", {}

    if has_contact:
        out: dict = {}
        customer_name = _extract_customer_name_from_account_phrase(normalized_goal)
        if customer_name:
            out["customer_name"] = customer_name
        return "CONTACT_LIST", out
    if has_contract:
        return "CONTRACT_LIST", {}
    if has_opportunity:
        return "OPPORTUNITY_LIST", {}
    if has_account:
        return "ACCOUNT_LIST", {}
    return None


def _heuristic_fallback_intent(normalized_goal: str, intent: str, entities: dict) -> tuple[str, dict, dict]:
    out = dict(entities or {})
    heuristic_trace = {"applied": False, "reason": ""}
    if intent != "UNKNOWN":
        return intent, out, heuristic_trace

    if (
        "account" in normalized_goal
        and any(v in normalized_goal for v in _DETAIL_HINTS)
        and any(v in normalized_goal for v in ("toan bo", "toàn bộ", "lien quan", "liên quan", "cung voi", "cùng với"))
        and any(t in normalized_goal for t in ("contact", "contract", "opportunity", "opportunities", "opp"))
    ):
        guessed = _extract_customer_name_from_account_phrase(normalized_goal)
        if guessed:
            out["keyword"] = guessed
        heuristic_trace["applied"] = True
        heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_ACCOUNT_360"
        return "ACCOUNT_360", out, heuristic_trace

    if any(v in normalized_goal for v in ("toan bo", "toàn bộ", "lien quan", "liên quan", "cung voi", "cùng với")):
        extracted = extract_entities(normalized_goal)
        tables = extracted.get("mentioned_tables", []) if isinstance(extracted, dict) else []
        if isinstance(tables, list) and len(tables) >= 2:
            root_table = "hbl_account" if "hbl_account" in tables else str(tables[0])
            out["root_table"] = root_table
            out["include_tables"] = [str(t) for t in tables if str(t) and str(t) != root_table]
            out["keyword"] = _extract_customer_name_from_account_phrase(normalized_goal) or normalized_goal
            out["limit"] = 20
            heuristic_trace["applied"] = True
            heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_DYNAMIC_QUERY"
            return "DYNAMIC_QUERY", out, heuristic_trace

    if any(v in normalized_goal for v in _CREATE_VERBS) and any(
        t in normalized_goal for t in ("account", "accounts", "acocunt", "acount", "accout")
    ):
        inferred_intent = "ACCOUNT_CREATE"
        for p in _ACCOUNT_NAME_PATTERNS:
            m = p.search(normalized_goal)
            if m:
                out["name"] = m.group(1).strip()
                break
        heuristic_trace["applied"] = True
        heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_ACCOUNT_CREATE"
        return inferred_intent, out, heuristic_trace

    if any(v in normalized_goal for v in _COMPARE_VERBS) and any(
        t in normalized_goal for t in ("account", "accounts", "acocunt", "acount", "accout")
    ):
        heuristic_trace["applied"] = True
        heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_ACCOUNT_COMPARE"
        return "ACCOUNT_COMPARE", out, heuristic_trace

    if any(v in normalized_goal for v in _CREATE_VERBS) and "contact" in normalized_goal:
        heuristic_trace["applied"] = True
        heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_CONTACT_CREATE"
        return "CONTACT_CREATE", out, heuristic_trace

    if any(v in normalized_goal for v in _COMPARE_VERBS) and "contact" in normalized_goal:
        heuristic_trace["applied"] = True
        heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_CONTACT_COMPARE"
        return "CONTACT_COMPARE", out, heuristic_trace

    if any(v in normalized_goal for v in _CREATE_VERBS) and "contract" in normalized_goal:
        heuristic_trace["applied"] = True
        heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_CONTRACT_CREATE"
        return "CONTRACT_CREATE", out, heuristic_trace

    if any(v in normalized_goal for v in _COMPARE_VERBS) and "contract" in normalized_goal:
        heuristic_trace["applied"] = True
        heuristic_trace["reason"] = "fallback_from_UNKNOWN_to_CONTRACT_COMPARE"
        return "CONTRACT_COMPARE", out, heuristic_trace

    if "contact" in normalized_goal and any(v in normalized_goal for v in _DETAIL_HINTS):
        inferred_tool = "get_contact_details"
    elif out.get("contract_id"):
        inferred_tool = "get_contract_details"
    else:
        extracted = extract_entities(normalized_goal)
        inferred_tool = infer_best_tool_for_tables(extracted.get("mentioned_tables", []), default_tool="list_accounts")
        if not inferred_tool:
            case_match = match_case(normalized_goal)
            if case_match and isinstance(case_match.get("case"), dict):
                inferred_tool = str(case_match["case"].get("expected_tool", "")).strip()
    tool_to_intent = {v: k for k, v in INTENT_TOOL_HINT.items()}
    inferred_intent = tool_to_intent.get(inferred_tool, "UNKNOWN")
    if inferred_intent == "UNKNOWN":
        return intent, out, heuristic_trace

    has_account = any(t in normalized_goal for t in ("account", "accounts", "acocunt", "acount", "accout"))
    if inferred_intent == "CONTACT_LIST" and has_account and not out.get("customer_name"):
        for p in _ACCOUNT_NAME_PATTERNS:
            m = p.search(normalized_goal)
            if m:
                out["customer_name"] = m.group(1).strip()
                break
        if not out.get("customer_name"):
            # fallback nhẹ: lấy cụm sau token account/acocunt
            marker = None
            for candidate in (" account ", " acocunt ", " acount ", " accout "):
                if candidate in f" {normalized_goal} ":
                    marker = candidate.strip()
                    break
            if marker:
                tail = normalized_goal.split(marker, 1)[-1]
                tail = re.sub(r"^(la|là|is)\s+", "", tail).strip()
                if tail:
                    out["customer_name"] = tail

    heuristic_trace["applied"] = True
    heuristic_trace["reason"] = f"fallback_from_UNKNOWN_to_{inferred_intent}_via_{inferred_tool}"
    return inferred_intent, out, heuristic_trace


def perception_node(state: dict):
    goal = state.get("goal", "")
    requested_role = "DEFAULT"

    clean_goal = clean_goal_text(goal)
    normalized_goal = normalize_goal_text(clean_goal)
    extracted = extract_entities(clean_goal)
    intent_trace = {}
    fast_path = _fast_path_intent_entities(normalized_goal)
    if fast_path:
        intent, entities = fast_path
        intent_trace = {
            "intent_parser_input": {
                "goal": clean_goal,
                "normalized_goal": normalized_goal,
                "mode": "fast_path",
            },
            "intent_parser_output": {
                "intent": intent,
                "entities": entities,
                "response_tokens_est": 0,
            },
        }
    else:
        try:
            intent, entities, intent_trace = llm_parse_intent_entities(clean_goal, normalized_goal)
        except Exception:
            intent = "UNKNOWN"
            entities = {}
    intent, entities, heuristic_trace = _heuristic_fallback_intent(normalized_goal, intent, entities)
    if isinstance(extracted.get("extracted_entities"), dict):
        for k, v in extracted["extracted_entities"].items():
            if v not in (None, ""):
                entities[k] = v

    order_id = extract_order_contract_id(normalized_goal)
    if order_id and not entities.get("contract_id"):
        entities["contract_id"] = order_id

    keyword = str(entities.get("keyword", "")).strip()
    if intent.endswith("_LIST") and normalize_goal_text(keyword) in PERCEPTION_GENERIC_LIST_KEYWORDS:
        keyword = ""
    if entities.get("bd_owner_id") or entities.get("am_sales_id"):
        keyword = ""
    entities["keyword"] = keyword
    normalized_request = resolve_request(intent, entities)

    role = requested_role

    planner_goal = keyword if intent == "ACCOUNT_LIST" and keyword else clean_goal

    return {
        "goal": clean_goal,
        "normalized_goal": normalized_goal,
        "planner_goal": planner_goal,
        "entity_extract": extracted,
        "intent": intent,
        "entities": normalized_request.entities,
        "request_contract": normalized_request.model_dump(),
        "role": role,
        "status": "NORMALIZED",
        "trace": {
            **intent_trace,
            "heuristic_fallback": heuristic_trace,
            "identity_entities": extracted.get("identities", []),
            "perception_tokens_est": {
                "goal_tokens_est": estimate_tokens(goal),
                "normalized_goal_tokens_est": estimate_tokens(normalized_goal),
                "entities_tokens_est": estimate_tokens(normalized_request.entities),
            },
        },
    }
