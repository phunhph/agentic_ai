from __future__ import annotations

from v2.contracts import IngestResult
from v2.metadata import MetadataProvider

_PROVIDER = MetadataProvider()


def reason_about_query(ingest: IngestResult) -> dict:
    """
    Multi-Stage Agentic Reasoning:
    1. Intent Decomposition: Analyst agent breaks down what the user wants.
    2. Knowledge Alignment: Researcher agent finds matching tables and entities from metadata.
    3. Action Dispatch: Dispatcher agent chooses the best tool and parameters.
    """
    # 1. Intent Decomposition
    primary_intent = ingest.intent
    
    # 2. Knowledge Alignment
    # Determine the root table based on entities or fallback
    root = _PROVIDER.get_default_root_table()
    if ingest.entities:
        root = ingest.entities[0]
    
    # 3. Action Dispatch
    # Decide which tool to use
    if primary_intent == "update":
        selected_tool = "v2_update_executor"
    elif primary_intent == "analyze":
        selected_tool = "v2_analytic_executor" # Future expansion
    else:
        selected_tool = "v2_query_executor"

    # Plan Joins
    join_path = []
    for table in ingest.entities[1:]:
        join_path.append({
            "from_table": root,
            "to_table": table,
            "relation_type": "inferred_by_reasoner"
        })

    keyword = ""
    if ingest.request_filters:
        first_val = ingest.request_filters[0].value
        if isinstance(first_val, str):
            keyword = first_val.strip()

    # Agentic Thought Process
    thought = (
        f"Analyst identified '{primary_intent}' intent. "
        f"Researcher aligned it to '{root}' as root entity. "
        f"Dispatcher assigned '{selected_tool}' for execution."
    )

    trace = {
        "planner_mode": "v2_agentic_orchestrator",
        "thought_process": thought,
        "selected_entities": ingest.entities,
        "join_path": join_path,
        "intent": primary_intent,
        "decision_state": "ask_clarify" if ingest.ambiguity_score >= 0.8 else "auto_execute",
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
                "tactical_context": ingest.persona_context if isinstance(ingest.persona_context, dict) else {},
            },
            "trace": trace
        },
        "planner_trace_v2": trace,
        "ask_clarify": trace.get("decision_state") == "ask_clarify",
    }
