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
)
from tools.tool_registry import TOOL_REGISTRY

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+")


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_PATTERN.finditer(text or "")}


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
    compare_keys = ("contract_id", "customer_name", "bd_owner_id", "am_sales_id")
    for k in compare_keys:
        cur = str(current.get(k, "")).strip().lower()
        old = str(learned.get(k, "")).strip().lower()
        if cur and old and cur != old:
            return False, f"entity_mismatch:{k}"
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


def _structure_compatible(
    *,
    current_intent: str,
    current_tables: list[str],
    current_entities: dict[str, Any],
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
        hit_tables = set(extract_entities(hit_ref_query).get("mentioned_tables", []) or [])
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
    case_match = match_case(goal)
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
    extracted = state.get("entity_extract") if isinstance(state.get("entity_extract"), dict) else extract_entities(goal)
    
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
    intent_tool = INTENT_TOOL_HINT.get(current_intent, "")
    if intent_tool and intent_tool in MATRIX_ALLOWED_TOOLS:
        # Khi intent đã rõ ràng, ưu tiên tool theo intent để tránh drift sang bảng khác.
        tool = intent_tool
    if tool not in MATRIX_ALLOWED_TOOLS:
        tool = inferred_default
    args = _build_tool_args(tool, keyword, entities)

    # 3. Tự động vẽ đường JOIN (Pathfinding Evolution)
    join_path: list[dict[str, Any]] = []
    if len(mentioned_tables) >= 2:
        paths = provider.find_paths(mentioned_tables[0], mentioned_tables[1], max_depth=MATRIX_MAX_PATH_DEPTH)
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