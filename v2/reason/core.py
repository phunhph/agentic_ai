from __future__ import annotations

from collections import deque

from v2.contracts import IngestResult
from v2.metadata import MetadataProvider

_PROVIDER = MetadataProvider()


def _pick_root_from_query(ingest: IngestResult) -> str:
    if not ingest.entities:
        return _PROVIDER.get_default_root_table()
    lowered = str(getattr(ingest, "raw_query", "") or "").lower()
    if not lowered:
        return ingest.entities[0]
    # Prefer entity that appears first in user query.
    best_entity = ingest.entities[0]
    best_pos = 10**9
    for entity in ingest.entities:
        aliases = [k for k, v in _PROVIDER.iter_alias_items() if v == entity]
        for alias in aliases:
            pos = lowered.find(str(alias).lower())
            if pos >= 0 and pos < best_pos:
                best_pos = pos
                best_entity = entity
    return best_entity


def _find_table_path(src: str, dst: str) -> list[str]:
    if src == dst:
        return [src]
    edges = getattr(_PROVIDER.metadata, "lookup_edges", set()) or set()
    if not edges:
        return []
    graph: dict[str, set[str]] = {}
    for a, b in edges:
        graph.setdefault(a, set()).add(b)
    q = deque([[src]])
    visited = {src}
    while q:
        path = q.popleft()
        cur = path[-1]
        neighbors = sorted(
            graph.get(cur, set()),
            key=lambda n: (0 if str(n).startswith("hbl_") else 1, str(n)),
        )
        for nxt in neighbors:
            if nxt in visited:
                continue
            npath = path + [nxt]
            if nxt == dst:
                return npath
            visited.add(nxt)
            q.append(npath)
    return []


def _pick_reasoning_mode(ingest: IngestResult) -> str:
    frame = ingest.persona_context.get("intent_frame", {}) if isinstance(ingest.persona_context, dict) else {}
    mode = str(frame.get("reasoning_mode", "")).strip()
    if mode:
        return mode
    if ingest.intent == "analyze":
        return "aggregate_report"
    if ingest.request_filters:
        return "scoped_retrieval"
    return "generic_retrieval"


def reason_about_query(ingest: IngestResult) -> dict:
    """
    Multi-Stage Agentic Reasoning:
    1. Intent Decomposition: Analyst agent breaks down what the user wants.
    2. Knowledge Alignment: Researcher agent finds matching tables and entities from metadata.
    3. Action Dispatch: Dispatcher agent chooses the best tool and parameters.
    """
    # 1. Intent Decomposition
    primary_intent = ingest.intent
    reasoning_mode = _pick_reasoning_mode(ingest)
    
    # 2. Knowledge Alignment
    # Determine the root table based on entities or fallback
    root = _pick_root_from_query(ingest)
    
    # 3. Action Dispatch
    # Decide which tool to use
    if primary_intent == "update":
        selected_tool = "v2_update_executor"
    elif reasoning_mode == "aggregate_report":
        selected_tool = "v2_analytic_executor"
    else:
        selected_tool = "v2_query_executor"

    # Plan Joins
    join_path = []
    for table in [e for e in ingest.entities if e != root]:
        table_path = _find_table_path(root, table)
        if len(table_path) >= 2:
            for i in range(len(table_path) - 1):
                join_path.append(
                    {
                        "from_table": table_path[i],
                        "to_table": table_path[i + 1],
                        "relation_type": "metadata_lookup_path",
                    }
                )
        else:
            join_path.append(
                {
                    "from_table": root,
                    "to_table": table,
                    "relation_type": "inferred_by_reasoner",
                }
            )

    keyword = ""
    if ingest.request_filters:
        first_val = ingest.request_filters[0].value
        if isinstance(first_val, str):
            keyword = first_val.strip()

    # Agentic Thought Process
    thought = (
        f"Analyst identified '{primary_intent}' intent. "
        f"Reasoning mode is '{reasoning_mode}'. "
        f"Researcher aligned it to '{root}' as root entity. "
        f"Dispatcher assigned '{selected_tool}' for execution."
    )

    intent_frame = ingest.persona_context.get("intent_frame", {}) if isinstance(ingest.persona_context, dict) else {}
    temporal = intent_frame.get("temporal", {}) if isinstance(intent_frame, dict) else {}
    work_intent = intent_frame.get("work_intent", {}) if isinstance(intent_frame, dict) else {}
    owner_targets = intent_frame.get("owner_targets", []) if isinstance(intent_frame, dict) else []
    identity_targets = intent_frame.get("identity_targets", []) if isinstance(intent_frame, dict) else []

    clarify_reasons: list[str] = []
    if reasoning_mode == "compass_query":
        has_time_scope = bool(
            isinstance(temporal, dict)
            and (temporal.get("today") or temporal.get("this_week") or temporal.get("this_month") or temporal.get("month_refs"))
        )
        if not root or root not in {"hbl_account", "hbl_contact", "hbl_opportunities", "hbl_contract"}:
            clarify_reasons.append("compass_missing_business_entity")
        if not has_time_scope and not bool(isinstance(work_intent, dict) and work_intent.get("running_scope")):
            clarify_reasons.append("compass_missing_time_scope")
    if reasoning_mode == "identity_lookup" and not identity_targets:
        clarify_reasons.append("identity_lookup_missing_identity_target")
    if reasoning_mode == "scoped_retrieval" and not ingest.request_filters and not owner_targets:
        clarify_reasons.append("scoped_retrieval_missing_scope_signal")

    trace = {
        "planner_mode": "v2_agentic_orchestrator",
        "thought_process": thought,
        "selected_entities": ingest.entities,
        "join_path": join_path,
        "intent": primary_intent,
        "reasoning_mode": reasoning_mode,
        "clarify_reasons": clarify_reasons,
        "decision_state": "ask_clarify" if ingest.ambiguity_score >= 0.8 or bool(clarify_reasons) else "auto_execute",
        "agent_consensus": {
            "analyst_confidence": 1.0 - ingest.ambiguity_score,
            "researcher_alignment": 0.9 if ingest.entities else 0.5,
            "dispatcher_match": 1.0
        }
    }

    return {
        "decision": {
            "thought": thought,
            "tool": selected_tool,
            "args": {
                "root_table": root,
                "keyword": keyword,
                "update_data": ingest.update_data if primary_intent == "update" else {},
                "reasoning_mode": reasoning_mode,
                "intent_frame": intent_frame if isinstance(intent_frame, dict) else {},
                "tactical_context": ingest.persona_context if isinstance(ingest.persona_context, dict) else {},
            },
            "trace": trace
        },
        "planner_trace_v2": trace,
        "ask_clarify": trace.get("decision_state") == "ask_clarify",
    }
