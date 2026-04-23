from __future__ import annotations

from v2.contracts import IngestResult


def reason_about_query(ingest: IngestResult) -> dict:
    root = "hbl_account"
    if ingest.entities:
        root = ingest.entities[0]
    join_path = []
    for table in ingest.entities[1:]:
        join_path.append(
            {
                "from_table": root,
                "to_table": table,
                "relation_type": "inferred",
            }
        )
    keyword = ""
    if ingest.request_filters:
        first_val = ingest.request_filters[0].value
        if isinstance(first_val, str):
            keyword = first_val.strip()
    decision = {
        "thought": f"Independent V2 reasoning from intent={ingest.intent}",
        "tool": "v2_query_executor",
        "args": {
            "root_table": root,
            "keyword": keyword,
        },
        "trace": {
            "planner_mode": "v2_independent_heuristic",
            "selected_entities": ingest.entities,
            "join_path": join_path,
            "decision_state": "ask_clarify" if ingest.ambiguity_score >= 0.8 else "auto_execute",
        },
    }
    trace = decision["trace"]
    return {
        "decision": decision,
        "planner_trace_v2": trace,
        "ask_clarify": trace.get("decision_state") == "ask_clarify",
    }
