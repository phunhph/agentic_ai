"""
pipeline/__init__.py
Master Pipeline — entry point duy nhất cho agentic pipeline.

run_pipeline() thay thế run_v2_pipeline() với import sạch từ các phase module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from core.contracts import LessonOutcome
from core.i18n import _resolve_locale, _t
from memory.session import get_session_context, update_session_context
from metadata.provider import MetadataProvider
from pipeline.phase1_ingest import ingest_query
from pipeline.phase1_ingest.context_merger import apply_context_to_ingest
from pipeline.phase2_reason import reason_about_query
from pipeline.phase2_reason.consistency import validate_reasoning_consistency
from pipeline.phase3_plan import compile_execution_plan
from pipeline.phase4_execute import execute_plan, validate_execution_plan
from pipeline.phase5_learn import evaluate_matrix_v2, record_outcome, train_matrix_v2
from pipeline.phase5_learn.firewall import evaluate_firewall, log_firewall_event, quarantine_sample, refresh_firewall_eval
from pipeline.phase5_learn.trainset import append_trainset_sample
from pipeline.phase5_learn.sample_builder import build_runtime_learning_sample
from pipeline.phase6_respond.agentic import build_agentic_response
from pipeline.phase6_respond.builder import build_clarify_suggestion, build_learning_summary
from pipeline.phase6_respond.tactician import apply_lean_personalization, apply_tactician_layer
from intelligence.persona import build_tactician_payload

_PROVIDER = MetadataProvider()


def _compute_learning_evidence(ingest: dict, execution_trace: dict) -> dict:
    ambiguity_raw = ingest.get("ambiguity_score", 1.0)
    try:
        ambiguity = float(ambiguity_raw)
    except (TypeError, ValueError):
        ambiguity = 1.0
    has_entities = bool(ingest.get("entities"))
    has_filters = bool(ingest.get("request_filters"))
    guardrail = execution_trace.get("guardrail", {}) if isinstance(execution_trace, dict) else {}
    guardrail_ok = bool(isinstance(guardrail, dict) and guardrail.get("ok", False))
    errors = guardrail.get("errors", []) if isinstance(guardrail, dict) and isinstance(guardrail.get("errors"), list) else []

    score = 0.0
    score += max(0.0, 1.0 - ambiguity) * 0.4
    score += 0.25 if has_entities else 0.0
    score += 0.2 if has_filters else 0.0
    score += 0.15 if guardrail_ok and not errors else 0.0
    return {
        "score": round(score, 4),
        "has_entities": has_entities,
        "has_filters": has_filters,
        "guardrail_ok": guardrail_ok,
        "ambiguity_score": round(ambiguity, 4),
        "eligible": score >= 0.45,
    }


def _build_learning_check(
    before_eval: dict,
    after_eval: dict,
    learning_update: dict,
    execution_success: bool,
) -> dict:
    tracked = [
        "tool_plan_correctness",
        "filter_fidelity",
        "join_correctness",
        "training_diversity",
        "graph_coverage",
    ]

    def _metric_value(report: dict, key: str) -> float:
        try:
            return float(report.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    deltas: dict[str, float] = {}
    improved = 0
    degraded = 0
    for k in tracked:
        b = _metric_value(before_eval, k)
        a = _metric_value(after_eval, k)
        d = round(a - b, 4)
        deltas[k] = d
        if d > 0.0005:
            improved += 1
        elif d < -0.0005:
            degraded += 1

    decision = str(learning_update.get("learning_decision", "unknown"))
    evidence = learning_update.get("evidence", {}) if isinstance(learning_update.get("evidence"), dict) else {}
    evidence_score = float(evidence.get("score", 0.0) or 0.0)

    checks: list[dict] = [
        {"name": "execution_has_signal", "passed": bool(execution_success)},
        {"name": "evidence_gate_passed", "passed": bool(evidence.get("eligible", False))},
        {"name": "learning_decision_valid", "passed": decision in {"appended", "skipped"}},
        {"name": "no_metric_degradation", "passed": degraded == 0},
        {"name": "knowledge_improved_or_stable", "passed": improved > 0 or degraded == 0},
    ]
    passed = all(bool(x.get("passed")) for x in checks)
    reasons = [str(x["name"]) for x in checks if not bool(x.get("passed"))]
    return {
        "passed": passed,
        "checks": checks,
        "failed_reasons": reasons,
        "metrics_delta": deltas,
        "summary": {
            "improved_metric_count": improved,
            "degraded_metric_count": degraded,
            "learning_decision": decision,
            "evidence_score": round(evidence_score, 4),
        },
    }


def _plan_fingerprint(plan_dict: dict) -> str:
    sanitized = dict(plan_dict or {})
    sanitized.pop("tactical_context", None)
    text = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_pipeline(query: str, role: str = "DEFAULT", session_id: str = "", lang: str = "auto") -> dict:
    """
    Entry point duy nhất của agentic pipeline.
    Thay thế run_v2_pipeline() từ v2/service.py.
    """
    locale = _resolve_locale(query, lang=lang)

    # Phase 1: Ingest
    ingest = ingest_query(query, role=role)
    session_context = get_session_context(session_id)
    ingest, context_usage = apply_context_to_ingest(ingest, session_context)

    # Phase 2: Reason
    reason_result = reason_about_query(ingest)
    if reason_result.get("ask_clarify"):
        saved_context = update_session_context(session_id, ingest, execution_plan={})
        assistant_response = _t(locale, "assistant_clarify")
        return {
            "decision_state": "ask_clarify",
            "message": "V2 cần thêm điều kiện để thực thi chính xác.",
            "assistant_response": assistant_response,
            "layers": {
                "ingest": {
                    "intent": ingest.intent,
                    "entities": ingest.entities,
                    "ambiguity_score": ingest.ambiguity_score,
                    "context_usage": context_usage,
                    "llm_trace": ingest.llm_trace,
                },
                "reason": reason_result.get("planner_trace_v2", {}),
                "execute": {},
                "learn": {},
            },
            "planner_trace_v2": reason_result.get("planner_trace_v2", {}),
            "execution_trace": {},
            "result": [],
            "conversation_context": {
                "session_id": session_id,
                "used": context_usage,
                "saved": bool(saved_context),
            },
            "llm_trace": ingest.llm_trace,
        }

    # Phase 3: Plan
    plan = compile_execution_plan(ingest, reason_result)
    plan_validation = validate_execution_plan(plan)
    consistency = validate_reasoning_consistency(
        ingest={
            "entities": ingest.entities,
            "request_filters": [asdict(f) for f in ingest.request_filters],
            "ambiguity_score": ingest.ambiguity_score,
        },
        plan=asdict(plan),
        planner_trace=reason_result.get("planner_trace_v2", {}),
    )
    trust_gate = {
        "plan_validation_ok": plan_validation.ok,
        "plan_validation_errors": plan_validation.errors,
        "consistency": consistency,
        "trusted": bool(plan_validation.ok and consistency.get("trusted")),
    }
    if not trust_gate["trusted"]:
        saved_context = update_session_context(session_id, ingest, execution_plan=asdict(plan))
        assistant_response = _t(locale, "assistant_untrusted")
        return {
            "decision_state": "ask_clarify",
            "message": "De an toan, V2 can lam ro yeu cau truoc khi thuc thi.",
            "assistant_response": assistant_response,
            "trust_gate": trust_gate,
            "layers": {
                "ingest": {
                    "intent": ingest.intent,
                    "entities": ingest.entities,
                    "ambiguity_score": ingest.ambiguity_score,
                    "context_usage": context_usage,
                    "llm_trace": ingest.llm_trace,
                },
                "reason": reason_result.get("planner_trace_v2", {}),
                "execute": {},
                "learn": {},
            },
            "planner_trace_v2": reason_result.get("planner_trace_v2", {}),
            "execution_trace": {},
            "result": [],
            "clarify_recommendation": build_clarify_suggestion(
                {"entities": ingest.entities, "request_filters": [asdict(f) for f in ingest.request_filters]},
                {
                    "guardrail": {"errors": plan_validation.errors},
                    "consistency_issues": consistency.get("issues", []),
                },
                locale=locale,
            ),
            "conversation_context": {
                "session_id": session_id,
                "used": context_usage,
                "saved": bool(saved_context),
            },
            "llm_trace": ingest.llm_trace,
        }

    # Phase 4: Execute
    execution = execute_plan(plan)
    layer_ingest = {
        "intent": ingest.intent,
        "entities": ingest.entities,
        "ambiguity_score": ingest.ambiguity_score,
        "request_filters": [asdict(f) for f in ingest.request_filters],
        "context_usage": context_usage,
        "persona_context": ingest.persona_context if isinstance(ingest.persona_context, dict) else {},
        "llm_trace": ingest.llm_trace,
    }
    layer_reason = reason_result.get("planner_trace_v2", {})
    layer_execute = execution.execution_trace

    # Phase 5: Learn
    runtime_sample = build_runtime_learning_sample(
        query=ingest.normalized_query,
        layer_ingest=layer_ingest,
        plan=asdict(plan),
        success=execution.success,
    )
    evidence = _compute_learning_evidence(layer_ingest, execution.execution_trace)
    firewall_event = evaluate_firewall(runtime_sample, layer_ingest, execution.execution_trace)
    log_firewall_event(firewall_event)
    if firewall_event.get("decision") == "quarantine":
        quarantine_sample(firewall_event, runtime_sample)
    firewall_eval = refresh_firewall_eval()

    if firewall_event.get("decision") == "allow":
        outcome = LessonOutcome(
            query=ingest.normalized_query,
            execution_plan=plan,
            success=execution.success,
            score_breakdown={},
            diagnostics={"execution_trace": execution.execution_trace},
        )
        learned = record_outcome(outcome)
    else:
        learned = {"score_breakdown": {}, "firewall_decision": firewall_event.get("decision")}

    before_eval = evaluate_matrix_v2()
    can_promote_sample = bool(
        evidence.get("eligible")
        and firewall_event.get("decision") == "allow"
        and execution.success
        and trust_gate.get("trusted", False)
    )
    if can_promote_sample:
        appended_sample = append_trainset_sample(runtime_sample)
    else:
        if not execution.success:
            blocked_reason = "non_success_execution_sample"
        elif not trust_gate.get("trusted", False):
            blocked_reason = "untrusted_runtime_sample"
        elif firewall_event.get("decision") != "allow":
            blocked_reason = "blocked_by_firewall"
        else:
            blocked_reason = "insufficient_learning_evidence"
        appended_sample = {
            "status": "skipped",
            "reason": blocked_reason,
            "evidence": evidence,
            "firewall": firewall_event,
            "quality_gate": {
                "execution_success": bool(execution.success),
                "trust_gate": bool(trust_gate.get("trusted", False)),
                "firewall_allow": firewall_event.get("decision") == "allow",
            },
        }

    if appended_sample.get("status") == "appended":
        train_artifact = train_matrix_v2()
        eval_report = evaluate_matrix_v2()
    else:
        train_artifact = {"version": "unchanged", "reason": appended_sample.get("reason", "skipped")}
        eval_report = evaluate_matrix_v2()

    learning_update = {
        "appended_sample": appended_sample,
        "learning_decision": appended_sample.get("status", "unknown"),
        "learning_phase": appended_sample.get("learning_phase", "phase_understanding_v2"),
        "evidence": evidence,
        "firewall_event": firewall_event,
        "firewall_eval": firewall_eval,
        "eval_before": before_eval,
        "train_artifact_version": train_artifact.get("version"),
        "eval_snapshot": eval_report,
    }
    layer_learn = {
        "lesson_score_breakdown": learned.get("score_breakdown", {}),
        "success": execution.success,
        "firewall_decision": firewall_event.get("decision"),
    }
    learning_check = _build_learning_check(
        before_eval=before_eval,
        after_eval=eval_report,
        learning_update=learning_update,
        execution_success=execution.success,
    )

    # Phase 6: Respond
    recommendation = ""
    if not execution.success:
        recommendation = build_clarify_suggestion(layer_ingest, execution.execution_trace, locale=locale)

    assistant_response = build_agentic_response(
        ingest.normalized_query,
        execution.data,
        execution.execution_trace,
        locale=locale,
        role=role,
    )
    assistant_response_before_lean = assistant_response

    tactician_payload = build_tactician_payload(
        query=ingest.normalized_query,
        persona_context=ingest.persona_context if isinstance(ingest.persona_context, dict) else {},
        rows=execution.data,
        execution_trace=execution.execution_trace,
    )
    assistant_response = apply_tactician_layer(assistant_response, tactician_payload, locale=locale)
    assistant_response = apply_lean_personalization(assistant_response, role=role, locale=locale)

    plan_dict = asdict(plan)
    reasoning_integrity = {
        "decision_state": "auto_execute",
        "reasoning_inputs": {
            "intent": ingest.intent,
            "entities": ingest.entities,
            "ambiguity_score": ingest.ambiguity_score,
        },
        "plan_fingerprint": _plan_fingerprint(plan_dict),
        "response_layers": {
            "before_lean": assistant_response_before_lean,
            "after_lean": assistant_response,
            "lean_changes_only_output": assistant_response_before_lean != assistant_response,
        },
    }

    learning_summary = build_learning_summary(learning_update, locale=locale)
    saved_context = update_session_context(session_id, ingest, execution_plan=plan_dict)

    return {
        "decision_state": "auto_execute",
        "assistant_response": assistant_response,
        "trust_gate": trust_gate,
        "layers": {
            "ingest": layer_ingest,
            "reason": layer_reason,
            "execute": layer_execute,
            "learn": {**layer_learn, "learning_update": learning_update},
        },
        "reasoning_integrity": reasoning_integrity,
        "planner_trace_v2": reason_result.get("planner_trace_v2", {}),
        "execution_plan": plan_dict,
        "execution_trace": execution.execution_trace,
        "result": execution.data,
        "tactician_payload": tactician_payload,
        "lesson_score_breakdown": learned.get("score_breakdown", {}),
        "learning_update": learning_update,
        "learning_check": learning_check,
        "learning_summary": learning_summary,
        "clarify_recommendation": recommendation,
        "conversation_context": {
            "session_id": session_id,
            "used": context_usage,
            "saved": bool(saved_context),
        },
        "llm_trace": ingest.llm_trace,
    }


# Backwards compat alias
run_v2_pipeline = run_pipeline
