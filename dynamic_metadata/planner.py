from __future__ import annotations
import re
from typing import Any
from agent.field_resolver import INTENT_TOOL_HINT
from core.metadata_provider import get_metadata_provider
from dynamic_metadata.case_memory import match_case
from dynamic_metadata.entity_extract import extract_entities
from dynamic_metadata.tool_inference import infer_best_tool_for_tables
from infra.settings import (
    MATRIX_ALLOWED_TOOLS,
    MATRIX_CASE_MIN_SIMILARITY,
    MATRIX_CASE_PRIOR_WEIGHT,
    MATRIX_DEFAULT_TOOL,
    MATRIX_MAX_PATH_DEPTH,
    STRICT_LEARNED_ONLY_MODE,
    STRICT_MIN_EVIDENCE_SIMILARITY,
    PLANNER_GENERIC_LIST_KEYWORDS,
    PLANNER_COMPLEXITY_BUDGET,
    UNCERTAINTY_BASE_ASK_CLARIFY_EVIDENCE,
    UNCERTAINTY_CASE_SUCCESS_BONUS_MAX,
    UNCERTAINTY_LEARNING_SCORE_BONUS_MAX,
)
from tools.tool_registry import TOOL_REGISTRY

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+")
_PLANNER_CACHE_MAX_SIZE = 256
_CASE_MATCH_CACHE: dict[str, dict[str, Any] | None] = {}
_ENTITY_EXTRACT_CACHE: dict[str, dict[str, Any]] = {}
_JOIN_PATH_CACHE: dict[tuple[str, str, int], list[dict[str, Any]]] = {}


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_PATTERN.finditer(text or "")}


def _cache_set(cache: dict[Any, Any], key: Any, value: Any) -> None:
    if key not in cache and len(cache) >= _PLANNER_CACHE_MAX_SIZE:
        cache.pop(next(iter(cache)))
    cache[key] = value


def _cached_match_case(goal: str) -> dict[str, Any] | None:
    cache_key = str(goal or "").strip().lower()
    if cache_key in _CASE_MATCH_CACHE:
        return _CASE_MATCH_CACHE[cache_key]
    value = match_case(goal)
    _cache_set(_CASE_MATCH_CACHE, cache_key, value)
    return value


def _cached_extract_entities(query: str) -> dict[str, Any]:
    cache_key = str(query or "").strip().lower()
    if cache_key in _ENTITY_EXTRACT_CACHE:
        return _ENTITY_EXTRACT_CACHE[cache_key]
    value = extract_entities(query)
    _cache_set(_ENTITY_EXTRACT_CACHE, cache_key, value)
    return value


def _cached_find_path(provider, from_table: str, to_table: str, max_depth: int) -> list[dict[str, Any]]:
    key = (str(from_table), str(to_table), int(max_depth))
    if key in _JOIN_PATH_CACHE:
        return _JOIN_PATH_CACHE[key]
    paths = provider.find_paths(from_table, to_table, max_depth=max_depth)
    join_path: list[dict[str, Any]] = []
    if paths:
        join_path = [
            {
                "from_table": edge.from_table,
                "to_table": edge.to_table,
                "relation_type": edge.relation_type,
                "join_table": edge.join_table,
                "choice_group": edge.choice_group,
            }
            for edge in paths[0]
        ]
    _cache_set(_JOIN_PATH_CACHE, key, join_path)
    return join_path


def _build_tool_args(tool_name: str, keyword: str, entities: dict[str, Any]) -> dict[str, Any]:
    hints = TOOL_REGISTRY.get(tool_name, {}).get("arg_hints", []) or []
    args: dict[str, Any] = {}
    for hint in hints:
        if hint in entities and entities.get(hint) not in (None, ""):
            args[hint] = entities.get(hint)
        elif hint == "keyword":
            args["keyword"] = keyword
    if "customer_name" in hints and "customer_name" not in args:
        args["customer_name"] = entities.get("customer_name") or None
    return args


def _entities_compatible(current: dict[str, Any], learned: dict[str, Any]) -> tuple[bool, str]:
    compare_keys = ("contract_id", "customer_name", "contact_id", "bd_owner_id", "am_sales_id", "assignee_id", "root_table")
    for k in compare_keys:
        cur = str(current.get(k, "")).strip().lower()
        old = str(learned.get(k, "")).strip().lower()
        if cur and old and cur != old:
            return False, f"entity_mismatch:{k}"
    cur_kw = str(current.get("keyword", "")).strip().lower()
    old_kw = str(learned.get("keyword", "")).strip().lower()
    if cur_kw and old_kw:
        cur_tokens = set(cur_kw.split())
        old_tokens = set(old_kw.split())
        if cur_tokens and old_tokens and cur_tokens.isdisjoint(old_tokens):
            return False, "entity_mismatch:keyword_scope"
    return True, ""


def _tool_family(tool_name: str) -> str:
    tool = str(tool_name or "").strip().lower()
    if "contact" in tool:
        return "contact"
    if "contract" in tool:
        return "contract"
    if "account" in tool:
        return "account"
    return "other"


def _condition_keys(entities: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for k, v in (entities or {}).items():
        if v in (None, "", [], {}):
            continue
        out.add(str(k).strip().lower())
    return out


def _can_use_intent_fast_path(*, current_intent: str, intent_tool: str, entities: dict[str, Any], keyword: str) -> tuple[bool, str]:
    if not current_intent or current_intent == "UNKNOWN":
        return False, "intent_unknown"
    if not intent_tool or intent_tool not in MATRIX_ALLOWED_TOOLS:
        return False, "intent_tool_unavailable"

    if current_intent.endswith("_LIST"):
        # LIST intents are deterministic enough to bypass expensive autonomous scoring.
        return True, "list_intent_fast_path"

    core_entity_keys = ("contract_id", "customer_name", "bd_owner_id", "am_sales_id", "assignee_id")
    if any(entities.get(k) not in (None, "") for k in core_entity_keys):
        return True, "core_entity_fast_path"
    if str(keyword or "").strip():
        return True, "keyword_fast_path"
    return False, "insufficient_signal"


def _resolve_decision_state(
    *,
    strict_blocked: bool,
    current_intent: str,
    mentioned_tables: list[str],
    entities: dict[str, Any],
    knowledge_hits: list[dict],
    case_similarity: float,
    case_success_ratio: float,
    calibrated_evidence_floor: float,
) -> tuple[str, float, str]:
    core_entity_keys = ("contract_id", "customer_name", "bd_owner_id", "am_sales_id", "assignee_id")
    has_core_entities = any(entities.get(k) not in (None, "") for k in core_entity_keys)
    has_table_signal = bool(mentioned_tables)
    has_learned_hits = bool(knowledge_hits)
    has_intent_signal = bool(current_intent and current_intent != "UNKNOWN")

    confidence = 0.0
    if has_intent_signal:
        confidence += 0.2
    if has_table_signal:
        confidence += 0.2
    if has_core_entities:
        confidence += 0.3
    if has_learned_hits:
        confidence += 0.2
    confidence += min(0.1, max(0.0, case_similarity) * 0.1)
    confidence += min(0.1, max(0.0, case_success_ratio) * 0.1)

    if strict_blocked:
        return "safe_block", round(confidence, 3), "strict_learned_only_mode_blocked"
    if not has_intent_signal and not has_table_signal and not has_core_entities and case_similarity < 0.4:
        return "ask_clarify", round(confidence, 3), "low_signal_ambiguous_query"
    if not has_learned_hits and case_similarity < calibrated_evidence_floor and not (
        has_intent_signal and (has_table_signal or has_core_entities)
    ):
        return "ask_clarify", round(confidence, 3), "low_evidence_without_learning_hit"
    return "auto_execute", round(confidence, 3), "sufficient_signal"


def _compute_calibrated_evidence_floor(
    *,
    knowledge_hits: list[dict],
    case_success_ratio: float,
) -> tuple[float, dict[str, float]]:
    learning_scores: list[float] = []
    for hit in knowledge_hits or []:
        if not isinstance(hit, dict):
            continue
        raw = hit.get("score", hit.get("final_match_score", 0.0))
        try:
            learning_scores.append(float(raw or 0.0))
        except (TypeError, ValueError):
            continue
    avg_learning_score = (sum(learning_scores) / len(learning_scores)) if learning_scores else 0.0
    learning_bonus = min(
        UNCERTAINTY_LEARNING_SCORE_BONUS_MAX,
        max(0.0, avg_learning_score) * UNCERTAINTY_LEARNING_SCORE_BONUS_MAX,
    )
    case_bonus = min(
        UNCERTAINTY_CASE_SUCCESS_BONUS_MAX,
        max(0.0, case_success_ratio) * UNCERTAINTY_CASE_SUCCESS_BONUS_MAX,
    )
    evidence_floor = max(0.1, UNCERTAINTY_BASE_ASK_CLARIFY_EVIDENCE - learning_bonus - case_bonus)
    return round(evidence_floor, 4), {
        "base": float(UNCERTAINTY_BASE_ASK_CLARIFY_EVIDENCE),
        "avg_learning_score": round(avg_learning_score, 4),
        "learning_bonus": round(learning_bonus, 4),
        "case_success_ratio": round(max(0.0, case_success_ratio), 4),
        "case_bonus": round(case_bonus, 4),
    }


def _estimate_planner_complexity(
    *,
    mentioned_tables: list[str],
    knowledge_hits: list[dict],
    choice_constraints: list[dict[str, Any]],
    join_path: list[dict[str, Any]],
) -> int:
    # Lightweight complexity proxy to enforce "Simplicity First".
    score = 0
    score += min(4, len(mentioned_tables or []))
    score += min(4, len(knowledge_hits or []))
    score += min(4, len(choice_constraints or []))
    score += min(4, len(join_path or []))
    return score


def _build_tool_call_profile(
    *,
    tool: str,
    args: dict[str, Any],
    current_intent: str,
    mentioned_tables: list[str],
    join_path: list[dict[str, Any]],
    choice_constraints: list[dict[str, Any]],
    decision_state: str,
) -> dict[str, Any]:
    reserved_plan_keys = {"root_table", "include_tables", "limit", "id_filters", "filters"}
    filter_keys = [k for k, v in (args or {}).items() if k not in reserved_plan_keys and v not in (None, "", [], {})]
    plan_filters = args.get("filters") if isinstance(args.get("filters"), list) else []
    if plan_filters:
        filter_keys.extend(
            [
                str(f.get("field")).split(".", 1)[-1]
                for f in plan_filters
                if isinstance(f, dict) and str(f.get("field", "")).strip()
            ]
        )
    if isinstance(args.get("id_filters"), dict):
        filter_keys.extend([str(k) for k, v in args.get("id_filters", {}).items() if v not in (None, "")])
    has_id_filter = any(str(k).endswith("_id") or str(k).endswith("id") for k in filter_keys)
    has_keyword_filter = "keyword" in filter_keys
    has_customer_filter = "customer_name" in filter_keys
    has_choice_filter = bool(choice_constraints)
    is_multi_table = len(set(mentioned_tables or [])) >= 2 or bool(join_path)
    is_statistical = tool.startswith("compare_") or current_intent.endswith("_COMPARE")
    is_detail_lookup = "details" in tool or current_intent.endswith("_DETAILS")
    is_create = tool.startswith("create_") or current_intent.endswith("_CREATE")
    is_advisory = decision_state in {"ask_clarify", "safe_block"} or tool == "final_answer"

    if is_advisory:
        query_mode = "advisory_or_guardrail"
    elif tool == "dynamic_query":
        query_mode = "metadata_dynamic_query"
    elif tool == "get_account_360":
        query_mode = "multi_entity_overview"
    elif is_statistical:
        query_mode = "statistical_analysis"
    elif is_detail_lookup:
        query_mode = "detail_lookup"
    elif is_create:
        query_mode = "create_write"
    else:
        query_mode = "list_retrieval"

    if has_id_filter:
        search_strategy = "id_lookup"
    elif has_choice_filter:
        search_strategy = "choice_constraint_lookup"
    elif has_keyword_filter:
        search_strategy = "keyword_search"
    elif has_customer_filter:
        search_strategy = "relationship_filter"
    elif tool.startswith("list_"):
        search_strategy = "list_all_or_broad_scan"
    else:
        search_strategy = "intent_mapped"

    statistics_focus = None
    if tool == "compare_account_stats":
        statistics_focus = "account_count_by_owner"
    elif tool == "compare_contact_stats":
        statistics_focus = "contact_count_by_assignee"
    elif tool == "compare_contract_stats":
        statistics_focus = "contract_count_and_value_by_assignee"
    elif tool == "compare_opportunity_stats":
        statistics_focus = "opportunity_count_and_value_by_owner"

    return {
        "query_mode": query_mode,
        "search_strategy": search_strategy,
        "is_multi_table_query": is_multi_table,
        "table_scope": list(dict.fromkeys(mentioned_tables or [])),
        "join_depth": len(join_path or []),
        "has_filters": bool(filter_keys or has_choice_filter),
        "filter_keys": filter_keys,
        "choice_groups": sorted(
            list(
                {
                    str(c.get("choice_group"))
                    for c in (choice_constraints or [])
                    if isinstance(c, dict) and c.get("choice_group")
                }
            )
        ),
        "is_statistical": is_statistical,
        "statistics_focus": statistics_focus,
        "is_advisory": is_advisory,
        "advisory_mode": decision_state if is_advisory else "",
    }


def _infer_root_table(current_intent: str, mentioned_tables: list[str], selected_tool: str) -> str:
    if current_intent.startswith("ACCOUNT_") or "account" in selected_tool:
        return "hbl_account"
    if current_intent.startswith("CONTACT_") or "contact" in selected_tool:
        return "hbl_contact"
    if current_intent.startswith("CONTRACT_") or "contract" in selected_tool:
        return "hbl_contract"
    if current_intent.startswith("OPPORTUNITY_") or "opportunit" in selected_tool:
        return "hbl_opportunities"
    if mentioned_tables:
        return str(mentioned_tables[0])
    return "hbl_account"


def _build_dynamic_query_args(
    *,
    current_intent: str,
    selected_tool: str,
    mentioned_tables: list[str],
    entities: dict[str, Any],
    keyword: str,
    request_contract: dict[str, Any],
) -> dict[str, Any]:
    provider = get_metadata_provider()
    root_table = _infer_root_table(current_intent, mentioned_tables, selected_tool)
    include_tables = [t for t in list(dict.fromkeys(mentioned_tables or [])) if t and t != root_table]
    if not include_tables and root_table == "hbl_account":
        include_tables = ["hbl_contact", "hbl_opportunities", "hbl_contract"]
    table_spec = next((t for t in provider._schema.tables if t.name == root_table), None)
    root_pk = table_spec.primary_key if table_spec else ""
    id_filters: dict[str, Any] = {}
    if current_intent.endswith("_DETAILS") and root_pk:
        for k, v in (entities or {}).items():
            if v in (None, "", [], {}):
                continue
            if str(k).endswith("_id"):
                id_filters[root_pk] = v
                break
    filters = request_contract.get("filters", []) if isinstance(request_contract, dict) else []
    normalized_filters: list[dict[str, Any]] = []
    if isinstance(filters, list):
        for f in filters:
            if not isinstance(f, dict):
                continue
            field = str(f.get("field", "")).strip()
            op = str(f.get("op", "contains")).strip().lower()
            value = f.get("value")
            if not field or value in (None, ""):
                continue
            normalized_filters.append({"field": field, "op": "eq" if op == "eq" else "contains", "value": value})
    return {
        "root_table": root_table,
        "keyword": str(keyword or entities.get("keyword", "")).strip(),
        "include_tables": include_tables,
        "limit": 20,
        "id_filters": id_filters,
        "filters": normalized_filters,
    }


def _structure_compatible(
    *,
    current_intent: str,
    current_tables: list[str],
    current_entities: dict[str, Any],
    current_request_contract: dict[str, Any],
    hit: dict[str, Any],
) -> tuple[bool, str]:
    resolved_intent = str(hit.get("resolved_intent", "")).strip().upper()
    resolved_tool = str(hit.get("resolved_tool", "")).strip()
    if not resolved_tool and resolved_intent:
        resolved_tool = INTENT_TOOL_HINT.get(resolved_intent, "")

    if current_intent and resolved_intent and current_intent != resolved_intent:
        if _tool_family(INTENT_TOOL_HINT.get(current_intent, "")) != _tool_family(resolved_tool):
            return False, f"intent_family_mismatch:{current_intent}!={resolved_intent}"

    hit_ref_query = str(hit.get("original_query", "")).strip() or str(hit.get("correction_text", "")).strip()
    if hit_ref_query:
        hit_tables = set(_cached_extract_entities(hit_ref_query).get("mentioned_tables", []) or [])
        cur_tables = set(current_tables or [])
        if cur_tables and hit_tables and cur_tables.isdisjoint(hit_tables):
            return False, f"table_scope_mismatch:{sorted(list(cur_tables))}!={sorted(list(hit_tables))}"

    hit_entities = hit.get("resolved_entities") if isinstance(hit.get("resolved_entities"), dict) else {}
    cur_keys = _condition_keys(current_entities)
    hit_keys = _condition_keys(hit_entities)
    core_keys = {"contract_id", "customer_name", "bd_owner_id", "am_sales_id", "assignee_id"}
    cur_core = cur_keys.intersection(core_keys)
    hit_core = hit_keys.intersection(core_keys)
    if cur_core and hit_core and cur_core != hit_core:
        return False, f"condition_key_mismatch:{sorted(list(cur_core))}!={sorted(list(hit_core))}"

    # If current request has explicit filters, require hit to carry at least compatible entity hints.
    cur_filters = current_request_contract.get("filters", []) if isinstance(current_request_contract, dict) else []
    if isinstance(cur_filters, list) and cur_filters:
        expected_keys = set()
        for f in cur_filters:
            if not isinstance(f, dict):
                continue
            field = str(f.get("field", "")).strip().lower()
            if not field:
                continue
            expected_keys.add(field.split(".", 1)[-1])
        if expected_keys and hit_entities:
            hit_keys_expanded = {str(k).strip().lower() for k in hit_entities.keys()}
            if expected_keys.isdisjoint(hit_keys_expanded):
                return False, "filter_scope_mismatch:no_overlap_with_hit_entities"
    return True, ""


def _select_tool_autonomously(
    provider,
    *,
    goal: str,
    mentioned_tables: list[str],
    entities: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
    goal_tokens = _tokenize(goal)
    candidates = [t for t in TOOL_REGISTRY.keys() if t in MATRIX_ALLOWED_TOOLS]
    if not candidates:
        return MATRIX_DEFAULT_TOOL, {"reason": "no allowed tool candidates"}, None

    if entities.get("contract_id") and "get_contract_details" in candidates:
        return "get_contract_details", {"reason": "entity contract_id present", "score": 1000}, None

    best_tool = MATRIX_DEFAULT_TOOL if MATRIX_DEFAULT_TOOL in candidates else candidates[0]
    best_score = -1.0
    debug_scores: dict[str, float] = {}
    case_match = _cached_match_case(goal)
    case_info = None
    case_expected_tool = None
    case_expected_entities: set[str] = set()
    case_similarity = 0.0
    case_success_ratio = 0.0
    if case_match:
        case_data = case_match.get("case") if isinstance(case_match.get("case"), dict) else {}
        case_similarity = float(case_match.get("similarity", 0.0))
        case_expected_tool = str(case_data.get("expected_tool", "")).strip()
        expected_entities = case_data.get("expected_entities")
        usage_count = max(1, int(case_data.get("usage_count", 1)))
        success_count = int(case_data.get("success_count", 0))
        case_success_ratio = success_count / usage_count
        if isinstance(expected_entities, list):
            case_expected_entities = {str(x).strip() for x in expected_entities if str(x).strip()}
        case_info = {
            "query": case_data.get("query"),
            "expected_tool": case_expected_tool,
            "expected_entities": sorted(list(case_expected_entities)),
            "similarity": case_similarity,
            "success_ratio": round(case_success_ratio, 4),
        }

    for tool in candidates:
        info = TOOL_REGISTRY.get(tool, {})
        tool_terms = _tokenize(f"{tool} {info.get('description', '')}")
        overlap_goal = len(goal_tokens.intersection(tool_terms))
        score = float(overlap_goal)

        for table in mentioned_tables:
            alias_terms = provider.get_alias_terms_for_table(table)
            overlap_table = len(alias_terms.intersection(tool_terms))
            score += overlap_table * 3.0

        if case_similarity >= MATRIX_CASE_MIN_SIMILARITY and case_expected_tool:
            confidence_boost = 0.5 + (case_success_ratio / 2.0)
            if tool == case_expected_tool:
                score += MATRIX_CASE_PRIOR_WEIGHT * confidence_boost * case_similarity
            if mentioned_tables and case_expected_entities.intersection(set(mentioned_tables)):
                score += (MATRIX_CASE_PRIOR_WEIGHT / 2.0) * confidence_boost * case_similarity

        debug_scores[tool] = score
        if score > best_score:
            best_score = score
            best_tool = tool

    return best_tool, {"reason": "autonomous scoring", "score": best_score, "scores": debug_scores}, case_info

def plan_with_metadata(state: dict, knowledge_hits: list[dict] | None = None) -> dict:
    provider = get_metadata_provider()
    goal = state.get("goal", "")
    extracted = state.get("entity_extract") if isinstance(state.get("entity_extract"), dict) else _cached_extract_entities(goal)
    
    # Lấy tri thức từ Metadata và Kinh nghiệm quá khứ
    mentioned_tables = extracted["mentioned_tables"]
    choices = extracted["choices"]
    entities = state.get("entities", {}) if isinstance(state.get("entities"), dict) else {}
    current_intent = str(state.get("intent", "")).strip().upper()
    keyword_entity = str(entities.get("keyword", "")).strip()
    keyword = keyword_entity or extracted["keyword"]
    if current_intent.endswith("_LIST"):
        # Với list intent, ưu tiên keyword đã chuẩn hóa ở perception để tránh lọc nhiễu.
        keyword = keyword_entity
    normalized_keyword = " ".join(str(keyword or "").strip().lower().split())
    if current_intent.endswith("_LIST") and normalized_keyword in PLANNER_GENERIC_LIST_KEYWORDS:
        keyword = ""
    knowledge_hits = knowledge_hits or []

    # 1. Cơ chế Tự học (Learning First)
    if knowledge_hits:
        selected_experience = None
        rejection_reason = ""
        for hit in knowledge_hits:
            resolved_entities = hit.get("resolved_entities") if isinstance(hit.get("resolved_entities"), dict) else {}
            ok, reason = _entities_compatible(entities, resolved_entities)
            if not ok:
                rejection_reason = reason
                continue
            ok_struct, reason_struct = _structure_compatible(
                current_intent=current_intent,
                current_tables=mentioned_tables,
                current_entities=entities,
                current_request_contract=state.get("request_contract", {}) if isinstance(state.get("request_contract"), dict) else {},
                hit=hit,
            )
            if ok_struct:
                selected_experience = hit
                break
            rejection_reason = reason_struct
        if selected_experience:
            resolved_tool = str(selected_experience.get("resolved_tool", "")).strip()
            if not resolved_tool:
                resolved_intent = str(selected_experience.get("resolved_intent", "")).strip().upper()
                resolved_tool = INTENT_TOOL_HINT.get(resolved_intent, MATRIX_DEFAULT_TOOL)
            resolved_entities = (
                selected_experience.get("resolved_entities")
                if isinstance(selected_experience.get("resolved_entities"), dict)
                else {}
            )
            args = dict(resolved_entities)
            if keyword and "keyword" not in args:
                args["keyword"] = keyword
            if (
                resolved_tool == "list_contacts"
                and entities.get("customer_name")
                and "customer_name" not in args
            ):
                args["customer_name"] = entities.get("customer_name")
            if resolved_tool in {
                "list_accounts",
                "list_contacts",
                "list_contracts",
                "list_opportunities",
                "get_contact_details",
                "get_contract_details",
                "get_account_overview",
                "get_account_360",
            }:
                args = _build_dynamic_query_args(
                    current_intent=current_intent,
                    selected_tool=resolved_tool,
                    mentioned_tables=mentioned_tables,
                    entities=entities,
                    keyword=keyword,
                    request_contract=state.get("request_contract", {}),
                )
                resolved_tool = "dynamic_query"
            return {
                "thought": f"Bắt chước giải pháp đã thành công trong quá khứ cho case: {selected_experience.get('pattern')}",
                "tool": resolved_tool,
                "args": args,
                "trace": {
                    "planner_mode": "learned_evolution",
                    "experience_id": selected_experience.get("id"),
                    "knowledge_hits": knowledge_hits,
                    "selected_entities": mentioned_tables,
                    "choice_constraints": [],
                    "join_path": [],
                    "knowledge_reject_reason": "",
                },
            }
        # if all hits mismatch, continue with metadata reasoning
        knowledge_reject_reason = rejection_reason or "knowledge_hits_unusable"
    else:
        knowledge_reject_reason = ""

    # 2. Cơ chế Suy luận Động (Dynamic Reasoning)
    primary_table = mentioned_tables[0] if mentioned_tables else None
    intent_tool = INTENT_TOOL_HINT.get(current_intent, "")
    use_fast_path, fast_path_reason = _can_use_intent_fast_path(
        current_intent=current_intent,
        intent_tool=intent_tool,
        entities=entities,
        keyword=keyword,
    )
    case_info = None
    if use_fast_path:
        # Khi intent đã rõ ràng và có đủ tín hiệu, dùng fast-path để giảm latency.
        tool = intent_tool
        selector_trace = {"reason": "intent_fast_path", "detail": fast_path_reason, "score": None, "scores": {}}
    else:
        inferred_default = infer_best_tool_for_tables(
            mentioned_tables,
            allowed_tools=MATRIX_ALLOWED_TOOLS,
            default_tool=MATRIX_DEFAULT_TOOL,
        )
        tool, selector_trace, case_info = _select_tool_autonomously(
            provider,
            goal=extracted["normalized_goal"],
            mentioned_tables=mentioned_tables,
            entities=entities,
        )
        if tool not in MATRIX_ALLOWED_TOOLS:
            tool = inferred_default
        if (
            not current_intent
            and "hbl_contact" in set(mentioned_tables or [])
            and tool == "list_accounts"
            and "list_contacts" in MATRIX_ALLOWED_TOOLS
        ):
            # Avoid account drift for contact-scoped queries that mention account as relationship context.
            tool = "list_contacts"
            selector_trace["reason"] = "contact_scope_prefer_list_contacts"
    if tool not in MATRIX_ALLOWED_TOOLS:
        tool = MATRIX_DEFAULT_TOOL
    if tool == "get_account_360" and current_intent != "ACCOUNT_360":
        # Keep account-360 for explicit holistic-account intents only.
        tool = intent_tool if intent_tool in MATRIX_ALLOWED_TOOLS else MATRIX_DEFAULT_TOOL
    args = _build_tool_args(tool, keyword, entities)
    # Reduce hard-coded read-tools: route retrieval/detail/overview to dynamic query engine.
    if tool in {
        "list_accounts",
        "list_contacts",
        "list_contracts",
        "list_opportunities",
        "get_contact_details",
        "get_contract_details",
        "get_account_overview",
        "get_account_360",
    }:
        args = _build_dynamic_query_args(
            current_intent=current_intent,
            selected_tool=tool,
            mentioned_tables=mentioned_tables,
            entities=entities,
            keyword=keyword,
            request_contract=state.get("request_contract", {}),
        )
        tool = "dynamic_query"
        selector_trace["reason"] = f"{selector_trace.get('reason', '')}_routed_dynamic_query".strip("_")

    # 3. Tự động vẽ đường JOIN (Pathfinding Evolution)
    join_path: list[dict[str, Any]] = []
    if len(mentioned_tables) >= 2:
        join_path = _cached_find_path(
            provider,
            mentioned_tables[0],
            mentioned_tables[1],
            MATRIX_MAX_PATH_DEPTH,
        )

    # 4. Tự động mở rộng bộ lọc (Choice Expansion)
    choice_constraints: list[dict[str, Any]] = []
    dynamic_tables = [t.name for t in provider._schema.tables]
    expansion_targets = [t for t in [primary_table, *mentioned_tables, *dynamic_tables] if t]
    dedup_targets = list(dict.fromkeys(expansion_targets))
    for choice in choices:
        for table in dedup_targets:
            constraint = provider.expand_choice_filter(table, choice["group"], choice["label"])
            if constraint:
                choice_constraints.append(constraint)
                break

    strict_blocked = False
    strict_reason = ""
    case_similarity = float((case_info or {}).get("similarity", 0.0) if isinstance(case_info, dict) else 0.0)
    case_success_ratio = float((case_info or {}).get("success_ratio", 0.0) if isinstance(case_info, dict) else 0.0)
    calibrated_evidence_floor, evidence_calibration = _compute_calibrated_evidence_floor(
        knowledge_hits=knowledge_hits,
        case_success_ratio=case_success_ratio,
    )
    bootstrap_learning = bool(state.get("bootstrap_learning", False))
    if (
        STRICT_LEARNED_ONLY_MODE
        and not bootstrap_learning
        and not knowledge_hits
        and case_similarity < STRICT_MIN_EVIDENCE_SIMILARITY
    ):
        strict_blocked = True
        strict_reason = (
            f"no learned evidence: knowledge_hits=0 and case_similarity={case_similarity:.2f} "
            f"< {STRICT_MIN_EVIDENCE_SIMILARITY:.2f}"
        )
        tool = "final_answer"
        args = {}

    decision_state, decision_confidence, decision_reason = _resolve_decision_state(
        strict_blocked=strict_blocked,
        current_intent=current_intent,
        mentioned_tables=mentioned_tables,
        entities=entities,
        knowledge_hits=knowledge_hits,
        case_similarity=case_similarity,
        case_success_ratio=case_success_ratio,
        calibrated_evidence_floor=calibrated_evidence_floor,
    )
    complexity_score = _estimate_planner_complexity(
        mentioned_tables=mentioned_tables,
        knowledge_hits=knowledge_hits,
        choice_constraints=choice_constraints,
        join_path=join_path,
    )
    complexity_budget_exceeded = complexity_score > PLANNER_COMPLEXITY_BUDGET
    tool_call_profile = _build_tool_call_profile(
        tool=tool,
        args=args,
        current_intent=current_intent,
        mentioned_tables=mentioned_tables,
        join_path=join_path,
        choice_constraints=choice_constraints,
        decision_state=decision_state,
    )

    trace = {
        "planner_mode": "autonomous_metadata",
        "selected_entities": mentioned_tables,
        "join_path": join_path,
        "choice_constraints": choice_constraints,
        "knowledge_hits": knowledge_hits,
        "metadata_version": "db.json",
        "tool_selector": selector_trace,
        "matrix_case_match": case_info,
        "strict_learned_only_mode": STRICT_LEARNED_ONLY_MODE,
        "bootstrap_learning": bootstrap_learning,
        "strict_blocked": strict_blocked,
        "strict_reason": strict_reason,
        "knowledge_reject_reason": knowledge_reject_reason,
        "target_identities": extracted.get("identities", []),
        "decision_state": decision_state,
        "decision_confidence": decision_confidence,
        "decision_reason": decision_reason,
        "calibrated_evidence_floor": calibrated_evidence_floor,
        "evidence_calibration": evidence_calibration,
        "rejection_signals": {
            "knowledge_reject_reason": knowledge_reject_reason,
            "strict_reason": strict_reason,
            "decision_reason": decision_reason,
        },
        "complexity_score": complexity_score,
        "complexity_budget": PLANNER_COMPLEXITY_BUDGET,
        "complexity_budget_exceeded": complexity_budget_exceeded,
        "tool_call_profile": tool_call_profile,
    }

    return {
        "thought": (
            f"Suy luận tự động dựa trên đồ thị Metadata của bảng {primary_table or 'fallback'}."
            if not strict_blocked
            else "Không đủ bằng chứng đã học trong ma trận/knowledge, chặn truy vấn để tránh suy diễn ngoài học liệu."
        ),
        "tool": tool,
        "args": args,
        "trace": trace,
    }