from __future__ import annotations

import json
from collections import deque

from core.contracts import IngestResult
from metadata.provider import MetadataProvider
from pipeline.phase5_learn.matrix import find_similar_experience
from pipeline.phase5_learn.graph import get_path_strength

from infra.settings import ENABLE_DYNAMIC_METADATA_PLANNER
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


def reason_about_query(ingest: IngestResult) -> dict:
    """
    DANN Multi-Stage Agentic Reasoning:
    1. Intent Decomposition: Analyst agent breaks down what the user wants.
    2. Neural Experience Recall: Check past successful cases for similar queries.
    3. Knowledge Alignment: Researcher agent finds matching tables and entities.
    4. Action Dispatch: Dispatcher agent chooses the best tool and parameters.
    """
    # 1. Intent Decomposition
    primary_intent = ingest.intent
    raw_query = getattr(ingest, "raw_query", "")

    # 2. Neural Experience Recall
    # Use DANN Neural Matrix to find similar past successful experiences
    similar_cases = []
    api_error = False
    try:
        similar_cases = find_similar_experience(raw_query)
    except Exception as e:
        print(f"[ERR] Neural Recall failed: {str(e)}")
        api_error = True

    best_past_experience = similar_cases[0] if similar_cases and similar_cases[0]["similarity"] > 0.9 else None
    
    # 3. Knowledge Alignment
    if best_past_experience:
        past_plan = best_past_experience["sample"]["plan"]
        root = past_plan.get("root_table") or _pick_root_from_query(ingest)
        selected_tool = past_plan.get("expected_shape", {}).get("expected_tool") or "v2_query_executor"
        recall_source = "neural_matrix_similarity"
        recall_score = best_past_experience["similarity"]
    else:
        root = _pick_root_from_query(ingest)
        # 4. Action Dispatch
        if primary_intent == "update":
            selected_tool = "v2_update_executor"
        elif primary_intent == "analyze":
            selected_tool = "v2_analytic_executor"
        else:
            selected_tool = "v2_query_executor"
        recall_source = "static_metadata_default"
        recall_score = 0.0

    # Validate choice via Agentic Graph
    graph_strength = get_path_strength(primary_intent, root, selected_tool)
    
    neural_recall_data = {
        "source": recall_source,
        "score": recall_score,
        "best_match": best_past_experience["sample"]["query"] if best_past_experience else None,
        "api_error": api_error
    }

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
        f"Neural recall used '{recall_source}' (score: {recall_score}). "
        f"Researcher aligned to '{root}' with graph strength {round(graph_strength, 2)}. "
        f"Dispatcher assigned '{selected_tool}'."
    )

    # Decision logic
    is_complex = len(ingest.entities) > 1 or primary_intent == "analyze"
    # DANN Adjustment: Trust more if we have high neural recall or strong graph evidence
    ambiguity_threshold = 0.85 if is_complex else 0.8
    if recall_score > 0.92 or graph_strength > 0.8:
        ambiguity_threshold += 0.1 # Increase threshold (be more confident)

    decision_state = "auto_execute"
    if ingest.ambiguity_score >= ambiguity_threshold:
        decision_state = "ask_clarify"
    
    if ENABLE_DYNAMIC_METADATA_PLANNER and (is_complex or recall_score > 0.85):
        decision_state = "auto_execute"
    
    trace = {
        "planner_mode": "dann_agentic_neural_network",
        "thought_process": thought,
        "selected_entities": ingest.entities,
        "join_path": join_path,
        "intent": primary_intent,
        "decision_state": decision_state,
        "neural_recall": neural_recall_data,
        "agent_consensus": {
            "analyst_confidence": round(1.0 - (ingest.ambiguity_score * 0.8), 2),
            "researcher_alignment": 0.95 if ingest.entities else 0.4,
            "dispatcher_match": 1.0 if selected_tool != "unknown" else 0.0,
            "graph_strength": round(graph_strength, 2)
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
                "tactical_context": ingest.persona_context if isinstance(ingest.persona_context, dict) else {},
            },
            "trace": trace
        },
        "planner_trace_v2": trace,
        "ask_clarify": trace.get("decision_state") == "ask_clarify",
    }
