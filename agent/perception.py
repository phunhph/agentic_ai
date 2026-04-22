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


def _extract_customer_name_from_account_phrase(normalized_goal: str) -> str:
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
    tail = normalized_goal.split(marker, 1)[-1]
    tail = re.sub(r"^(la|là|is)\s+", "", tail).strip()
    return tail


def _fast_path_intent_entities(normalized_goal: str) -> tuple[str, dict] | None:
    """Rule-based fast path for common CRM commands to reduce LLM latency and intent drift."""
    has_contact = "contact" in normalized_goal
    has_contract = "contract" in normalized_goal
    has_opportunity = any(t in normalized_goal for t in ("opportunity", "opportunities", "ops", "cơ hội", "co hoi"))
    has_account = any(t in normalized_goal for t in ("account", "accounts", "acocunt", "acount", "accout"))
    is_create = any(v in normalized_goal for v in _CREATE_VERBS)
    is_compare = any(v in normalized_goal for v in _COMPARE_VERBS)

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

    if out.get("contract_id"):
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
