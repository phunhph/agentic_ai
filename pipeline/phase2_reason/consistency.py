def _validate_reasoning_consistency(ingest: dict, plan: dict, planner_trace: dict) -> dict:
    issues: list[str] = []
    entities = ingest.get("entities", []) if isinstance(ingest.get("entities"), list) else []
    root_table = str(plan.get("root_table", "")).strip()
    if entities and root_table and root_table not in entities:
        issues.append("root_not_in_detected_entities")

    request_filters = ingest.get("request_filters", []) if isinstance(ingest.get("request_filters"), list) else []
    where_filters = plan.get("where_filters", []) if isinstance(plan.get("where_filters"), list) else []
    if request_filters and not where_filters:
        issues.append("missing_where_filters_from_ingest")

    ambiguity_raw = ingest.get("ambiguity_score", 1.0)
    try:
        ambiguity = float(ambiguity_raw)
    except (TypeError, ValueError):
        ambiguity = 1.0
    decision_state = str((planner_trace or {}).get("decision_state", "auto_execute"))
    if ambiguity >= 0.8 and decision_state != "ask_clarify":
        issues.append("high_ambiguity_without_clarify")

    confidence = 1.0
    confidence -= 0.35 if "root_not_in_detected_entities" in issues else 0.0
    confidence -= 0.25 if "missing_where_filters_from_ingest" in issues else 0.0
    confidence -= 0.4 if "high_ambiguity_without_clarify" in issues else 0.0
    confidence = max(0.0, min(1.0, confidence))
    return {
        "issues": issues,
        "confidence": round(confidence, 4),
        "trusted": confidence >= 0.65 and not issues,
    }


# Public alias
validate_reasoning_consistency = _validate_reasoning_consistency
