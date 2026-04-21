from __future__ import annotations

import re
from typing import Any

from core.metadata_provider import get_metadata_provider


_NOISE = {
    "cho",
    "toi",
    "tôi",
    "hay",
    "hãy",
    "xem",
    "giup",
    "giúp",
    "danh",
    "sach",
    "danhsach",
    "liet",
    "ke",
    "liệt",
    "kê",
    "tim",
    "tìm",
    "kiem",
    "kiếm",
    "trong",
    "crm",
    "la",
    "là",
}


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", " ", (text or "").lower()).split())


def _extract_entities(goal: str) -> dict[str, Any]:
    normalized = _normalize(goal)
    tokens = normalized.split()
    provider = get_metadata_provider()

    mentioned_tables: list[str] = []
    for gram_len in (2, 1):
        for i in range(0, len(tokens) - gram_len + 1):
            gram = " ".join(tokens[i : i + gram_len])
            table = provider.resolve_alias(gram)
            if table and table not in mentioned_tables:
                mentioned_tables.append(table)

    choices: list[dict[str, str]] = []
    for group, options in provider._schema.choice_options.items():  # intentional internal access
        for option in options:
            label = str(option.get("label", "")).strip()
            if label and label.lower() in normalized:
                choices.append({"group": group, "label": label})

    keyword = " ".join([t for t in tokens if t not in _NOISE and not provider.resolve_alias(t)]).strip()
    return {
        "normalized_goal": normalized,
        "mentioned_tables": mentioned_tables,
        "choices": choices,
        "keyword": keyword,
    }


def plan_with_metadata(state: dict, knowledge_hits: list[dict] | None = None) -> dict:
    provider = get_metadata_provider()
    goal = state.get("goal", "")
    extracted = _extract_entities(goal)
    mentioned_tables = extracted["mentioned_tables"]
    choices = extracted["choices"]
    keyword = extracted["keyword"]
    knowledge_hits = knowledge_hits or []

    tool = "list_accounts"
    args: dict[str, Any] = {}
    fallback_reason = ""

    if "hbl_contract" in mentioned_tables:
        tool = "list_contracts"
        args = {"customer_name": keyword or None, "status": None}
    elif "hbl_account" in mentioned_tables:
        tool = "list_accounts"
        args = {"keyword": keyword}
    elif any(k in extracted["normalized_goal"] for k in ("thong ke", "thống kê", "bao cao", "báo cáo", "overview")):
        tool = "get_account_overview"
    else:
        fallback_reason = "No clear metadata entity; fallback to account listing"
        args = {"keyword": keyword}

    # Use highest-scored explicit lesson as override hint.
    if knowledge_hits:
        top = knowledge_hits[0]
        resolved_intent = str(top.get("resolved_intent", "")).strip().upper()
        resolved_entities = top.get("resolved_entities") if isinstance(top.get("resolved_entities"), dict) else {}
        if resolved_intent == "CONTRACT_LIST":
            tool = "list_contracts"
            args = {
                "customer_name": resolved_entities.get("customer_name") or keyword or None,
                "status": resolved_entities.get("status"),
            }
        elif resolved_intent == "CONTRACT_DETAILS":
            tool = "get_contract_details"
            args = {"contract_id": resolved_entities.get("contract_id")}
        elif resolved_intent == "ACCOUNT_OVERVIEW":
            tool = "get_account_overview"
            args = {}
        elif resolved_intent == "ACCOUNT_LIST":
            tool = "list_accounts"
            args = {"keyword": resolved_entities.get("keyword", keyword)}

    join_path: list[dict[str, str | None]] = []
    if len(mentioned_tables) >= 2:
        paths = provider.find_paths(mentioned_tables[0], mentioned_tables[1], max_depth=4)
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

    choice_constraints: list[dict[str, Any]] = []
    for choice in choices:
        for table in ("hbl_account", "hbl_contract", "hbl_opportunities", "hbl_contact"):
            expanded = provider.expand_choice_filter(table, choice["group"], choice["label"])
            if expanded:
                choice_constraints.append(expanded)
                break

    trace = {
        "planner_mode": "dynamic_metadata",
        "selected_entities": mentioned_tables,
        "join_path": join_path,
        "choice_constraints": choice_constraints,
        "knowledge_hits": knowledge_hits,
        "fallback_reason": fallback_reason,
    }

    return {
        "thought": "Metadata planner selected route based on schema graph and choice dictionary.",
        "tool": tool,
        "args": args,
        "trace": trace,
    }

