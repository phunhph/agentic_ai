from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import sqlalchemy as sa

from storage.database import engine
from v2.contracts import LessonOutcome, RequestFilter
from v2.execute import execute_plan, validate_execution_plan
from v2.ingest import ingest_query
from v2.learn import evaluate_matrix_v2, record_outcome, train_matrix_v2
from v2.learn.trainset import append_trainset_sample
from v2.memory import get_session_context, update_session_context
from v2.plan import compile_execution_plan
from v2.reason import reason_about_query


def _build_runtime_learning_sample(
    query: str,
    layer_ingest: dict,
    plan: dict,
    success: bool,
) -> dict:
    return {
        "normalized_query": str(query).strip().lower(),
        "intent": str(layer_ingest.get("intent", "unknown")).strip().lower(),
        "root_table": str(plan.get("root_table", "hbl_account")).strip() or "hbl_account",
        "entities": layer_ingest.get("entities", []) if isinstance(layer_ingest.get("entities"), list) else [],
        "filters": layer_ingest.get("request_filters", []) if isinstance(layer_ingest.get("request_filters"), list) else [],
        "join_plan": plan.get("join_path", []) if isinstance(plan.get("join_path"), list) else [],
        "expected_shape": {"expected_tool": "v2_query_executor"},
        "success_label": bool(success),
        "source": "runtime_feedback",
        "notes": "auto_update_from_empty_result" if not success else "auto_update_from_success_result",
    }


def _build_clarify_suggestion(ingest: dict, execution_trace: dict, locale: str = "vi") -> str:
    if not ingest.get("entities"):
        return _t(locale, "clarify_entities")
    filters = ingest.get("request_filters", [])
    if not filters:
        return _t(locale, "clarify_filters")
    guardrail = execution_trace.get("guardrail", {})
    if isinstance(guardrail, dict) and guardrail.get("errors"):
        return _t(locale, "clarify_guardrail")
    return _t(locale, "clarify_no_rows")


def _compute_learning_evidence(ingest: dict, execution_trace: dict) -> dict:
    ambiguity = float(ingest.get("ambiguity_score", 1.0) or 1.0)
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


def _format_value(value):
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _detect_locale(query: str) -> str:
    text = str(query or "").strip().lower()
    if not text:
        return "vi"
    vi_markers = ["thông tin", "danh sách", "liên quan", "yêu cầu", "không", "lấy", "giúp", "cho biết"]
    if any(token in text for token in vi_markers):
        return "vi"
    en_markers = ["list", "show", "details", "related", "contracts", "contacts", "opportunities", "please"]
    if sum(1 for token in en_markers if token in text) >= 2:
        return "en"
    return "vi"


def _resolve_locale(query: str, lang: str = "auto") -> str:
    candidate = str(lang or "auto").strip().lower()
    if candidate in {"vi", "en"}:
        return candidate
    return _detect_locale(query)


def _t(locale: str, key: str) -> str:
    vi = {
        "status_success": "Thành công",
        "status_no_data": "Không có dữ liệu phù hợp",
        "result_title": "Kết quả xử lý yêu cầu:",
        "status_label": "Trạng thái",
        "count_label": "Số bản ghi",
        "request_label": "Yêu cầu",
        "summary_label": "Tóm tắt dữ liệu (tối đa 5 bản ghi đầu)",
        "remaining_label": "Còn {n} bản ghi khác chưa hiển thị.",
        "recommendation_label": "Khuyến nghị",
        "no_data_recommendation": "Không tìm thấy bản ghi phù hợp với điều kiện hiện tại. Để tiếp tục, đề nghị bổ sung tiêu chí lọc cụ thể hơn (tên đối tượng, mã định danh, owner hoặc khoảng thời gian).",
        "clarify_entities": "Bạn hãy bổ sung đối tượng cụ thể (account/contact/contract/opportunity).",
        "clarify_filters": "Bạn hãy bổ sung điều kiện lọc (tên, mã, owner, date range) để truy vấn chính xác hơn.",
        "clarify_guardrail": "Kế hoạch bị chặn bởi guardrail, vui lòng điều chỉnh field/filter hợp lệ theo schema.",
        "clarify_no_rows": "Không có bản ghi khớp điều kiện hiện tại. Bạn có thể mở rộng filter hoặc đổi root entity.",
        "learn_not_updated": "Học tập: không cập nhật tri thức mới ({reason}).",
        "learn_updated": "Học tập: đã cập nhật ({mode}). Signature: {signature}",
        "learn_mode_new": "học mới một mẫu tri thức chưa từng có",
        "learn_mode_expand": "học bổ sung tri thức mới trong cùng nhóm intent",
        "learn_mode_contradiction": "học điều chỉnh cho signature đã có kết quả khác",
        "assistant_clarify": "Để đảm bảo độ chính xác, yêu cầu hiện tại cần được làm rõ trước khi thực thi. Vui lòng bổ sung đối tượng chính và điều kiện lọc cụ thể.",
        "assistant_untrusted": "Hệ thống tạm thời chưa thực thi vì đánh giá tin cậy chưa đạt ngưỡng an toàn. Vui lòng bổ sung thông tin để tăng độ chắc chắn của suy luận.",
    }
    en = {
        "status_success": "Success",
        "status_no_data": "No matching data",
        "result_title": "Request processing result:",
        "status_label": "Status",
        "count_label": "Record count",
        "request_label": "Request",
        "summary_label": "Data summary (up to first 5 records)",
        "remaining_label": "{n} more records are not shown.",
        "recommendation_label": "Recommendation",
        "no_data_recommendation": "No records match the current condition. To continue, please add more specific filters (entity name, identifier, owner, or time range).",
        "clarify_entities": "Please provide a specific target entity (account/contact/contract/opportunity).",
        "clarify_filters": "Please add filtering conditions (name, code, owner, date range) for a precise query.",
        "clarify_guardrail": "The plan is blocked by guardrails. Please adjust fields/filters to valid schema columns.",
        "clarify_no_rows": "No records match the current conditions. You can broaden filters or change the root entity.",
        "learn_not_updated": "Learning: no new knowledge update ({reason}).",
        "learn_updated": "Learning: updated ({mode}). Signature: {signature}",
        "learn_mode_new": "learned a brand new knowledge pattern",
        "learn_mode_expand": "expanded knowledge within the same intent group",
        "learn_mode_contradiction": "updated an existing signature with a different outcome",
        "assistant_clarify": "To ensure accuracy, this request needs clarification before execution. Please provide the primary target and specific filtering conditions.",
        "assistant_untrusted": "Execution is temporarily blocked because the trust score is below the safe threshold. Please provide more details to increase reasoning confidence.",
    }
    return (en if locale == "en" else vi).get(key, key)


def _clean_table_token(table_name: str) -> str:
    token = str(table_name or "").strip().lower()
    for prefix in ("hbl_", "cr987_", "mc_", "tbl_"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
    return token.strip("_")


def _clean_field_token(field_name: str) -> str:
    token = str(field_name or "").strip().lower()
    for prefix in ("hbl_", "cr987_", "mc_"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
    token = token.strip("_")
    if token.endswith("_id"):
        token = token[:-3]
    elif token.endswith("id"):
        token = token[:-2].rstrip("_")
    return token


def _humanize_words(text: str) -> str:
    words = [w for w in str(text or "").replace("_", " ").split() if w]
    return " ".join(w.capitalize() for w in words)


def _humanize_field_key(raw_key: str, locale: str = "vi") -> str:
    key = str(raw_key or "").strip()
    if not key:
        return "Field" if locale == "en" else "Trường dữ liệu"

    # Joined/derived fields: <table>__<field>
    if "__" in key:
        table_name, field_name = key.split("__", 1)
        table_label = _humanize_words(_clean_table_token(table_name))
        field_label = _humanize_words(_clean_field_token(field_name))
        if locale == "en":
            return f"{table_label} {field_label}".strip()
        return f"{field_label} ({table_label})".strip()

    # FK label enrichment: <field>_label
    if key.lower().endswith("_label"):
        base = key[:-6]
        base_label = _humanize_words(_clean_field_token(base))
        if locale == "en":
            return base_label or "Related info"
        return base_label or "Thông tin liên quan"

    # Regular field: try strip table prefix if exists
    if "." in key:
        _table_name, field_name = key.split(".", 1)
        return _humanize_words(_clean_field_token(field_name))
    return _humanize_words(_clean_field_token(key))


def _load_lookup_relations() -> list[dict]:
    path = Path("db.json")
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[dict] = []
    for rel in (raw.get("relations", {}).get("lookup", []) or []):
        if not isinstance(rel, dict):
            continue
        from_table = str(rel.get("from_table", "")).strip()
        from_field = str(rel.get("from_field", "")).strip()
        to_table = str(rel.get("to_table", "")).strip()
        to_field = str(rel.get("to_field", "")).strip()
        if from_table and from_field and to_table and to_field:
            out.append(
                {
                    "from_table": from_table,
                    "from_field": from_field,
                    "to_table": to_table,
                    "to_field": to_field,
                }
            )
    return out


def _is_uuid_like(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if len(text) != 36:
        return False
    chunks = text.split("-")
    if [len(c) for c in chunks] != [8, 4, 4, 4, 12]:
        return False
    hex_digits = set("0123456789abcdefABCDEF")
    return all(all(ch in hex_digits for ch in chunk) for chunk in chunks)


def _guess_label_column(table_name: str) -> str | None:
    try:
        table = sa.Table(table_name, sa.MetaData(), autoload_with=engine)
    except Exception:
        return None
    candidates: list[str] = []
    for col in table.columns.keys():
        c = str(col)
        lc = c.lower()
        if lc.endswith("_name") or lc.endswith("name"):
            candidates.append(c)
        elif "fullname" in lc or "full_name" in lc:
            candidates.append(c)
        elif lc in {"name", "fullname", "full_name"}:
            candidates.append(c)
    if candidates:
        candidates.sort(key=lambda x: (0 if "name" in x.lower() else 1, len(x)))
        return candidates[0]
    return None


def _resolve_fk_labels(root_table: str, rows: list[dict]) -> list[dict]:
    relations = _load_lookup_relations()
    rel_map: dict[str, dict] = {}
    for rel in relations:
        if rel.get("from_table") == root_table:
            rel_map[str(rel.get("from_field"))] = rel
    if not rel_map or not rows:
        return rows

    resolved_rows: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            resolved_rows.append(row)
            continue
        decorated = dict(row)
        for fk_field, rel in rel_map.items():
            fk_value = row.get(fk_field)
            if fk_value in (None, ""):
                continue
            target_table = str(rel.get("to_table"))
            target_pk = str(rel.get("to_field"))
            label_col = _guess_label_column(target_table)
            if not label_col:
                continue
            try:
                t = sa.Table(target_table, sa.MetaData(), autoload_with=engine)
                stmt = sa.select(t.c[label_col]).where(t.c[target_pk] == fk_value).limit(1)
                with engine.connect() as conn:
                    label = conn.execute(stmt).scalar_one_or_none()
                if label not in (None, ""):
                    decorated[f"{fk_field}_label"] = label
            except Exception:
                continue
        resolved_rows.append(decorated)
    return resolved_rows


def _pick_presentable_fields(row: dict, root_table: str = "") -> list[tuple[str, object]]:
    items = list(row.items())
    priority: list[tuple[str, object]] = []
    secondary: list[tuple[str, object]] = []
    hidden: list[tuple[str, object]] = []
    primary_name_key = f"{root_table}_name" if root_table else ""
    for k, v in items:
        lk = str(k).lower()
        if primary_name_key and lk == primary_name_key:
            priority.insert(0, (k, v))
            continue
        if lk.endswith("_label"):
            priority.append((k, v))
            continue
        if "name" in lk or "title" in lk or "label" in lk:
            priority.append((k, v))
            continue
        if lk.endswith("id") and _is_uuid_like(v):
            hidden.append((k, v))
            continue
        secondary.append((k, v))

    merged = priority + secondary
    if not merged:
        merged = hidden
    return merged[:4]


def _build_professional_response(query: str, rows: list[dict], execution_trace: dict, locale: str = "vi") -> str:
    if not rows:
        recommendation = _t(locale, "no_data_recommendation")
        return (
            f"{_t(locale, 'result_title')}\n"
            f"- {_t(locale, 'status_label')}: {_t(locale, 'status_no_data')}.\n"
            f"- {_t(locale, 'request_label')}: {query}\n"
            f"- {_t(locale, 'recommendation_label')}: {recommendation}"
        )

    row_count = int(execution_trace.get("row_count", len(rows)) or len(rows))
    root_table = str((execution_trace.get("plan", {}) or {}).get("root_table", "")).strip()
    resolved_rows = _resolve_fk_labels(root_table, rows) if root_table else rows
    preview = resolved_rows[:5]
    lines = [
        _t(locale, "result_title"),
        f"- {_t(locale, 'status_label')}: {_t(locale, 'status_success')}.",
        f"- {_t(locale, 'count_label')}: {row_count}.",
        f"- {_t(locale, 'request_label')}: {query}",
        f"- {_t(locale, 'summary_label')}:",
    ]
    for idx, row in enumerate(preview, start=1):
        if not isinstance(row, dict):
            lines.append(f"  {idx}. {_format_value(row)}")
            continue
        parts = []
        for k, v in _pick_presentable_fields(row, root_table=root_table):
            parts.append(f"{_humanize_field_key(k, locale=locale)}: {_format_value(v)}")
        lines.append(f"  {idx}. " + "; ".join(parts))
    if row_count > len(preview):
        lines.append(f"- {_t(locale, 'remaining_label').format(n=row_count - len(preview))}")
    return "\n".join(lines)


def _build_learning_summary(learning_update: dict, locale: str = "vi") -> str:
    decision = str(learning_update.get("learning_decision", "unknown"))
    appended = learning_update.get("appended_sample", {}) if isinstance(learning_update.get("appended_sample"), dict) else {}
    if decision != "appended":
        reason = str(appended.get("reason", "not_appended")).strip() or "not_appended"
        return _t(locale, "learn_not_updated").format(reason=reason)
    mode = str(appended.get("learning_mode", "new_signature")).strip() or "new_signature"
    signature = str(appended.get("signature", "")).strip()
    mode_text = {
        "new_signature": _t(locale, "learn_mode_new"),
        "intent_expansion": _t(locale, "learn_mode_expand"),
        "contradiction_update": _t(locale, "learn_mode_contradiction"),
    }.get(mode, mode)
    return _t(locale, "learn_updated").format(mode=mode_text, signature=signature)


def _metric_value(eval_report: dict, key: str) -> float:
    try:
        return float(eval_report.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


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


def _is_generic_list_like(query: str) -> bool:
    lowered = str(query or "").lower()
    generic_tokens = ["danh sách", "danh sach", "list", "liệt kê", "liet ke", "all "]
    return any(t in lowered for t in generic_tokens)


def _is_follow_up_query(query: str) -> bool:
    lowered = str(query or "").lower()
    follow_tokens = ["chỉ", "chi ", "tiếp", "them", "thêm", "với điều kiện", "with condition", "lọc", "filter", "liên quan", "related"]
    return any(t in lowered for t in follow_tokens)


def _apply_context_to_ingest(ingest, session_context: dict) -> tuple[object, dict]:
    if not session_context:
        return ingest, {"used": False, "source": "none"}
    prev_entities = session_context.get("entities", []) if isinstance(session_context.get("entities"), list) else []
    prev_filters = session_context.get("request_filters", []) if isinstance(session_context.get("request_filters"), list) else []
    used_entities = False
    used_filters = False
    used_intent = False

    if not ingest.entities and prev_entities:
        ingest.entities = [str(x).strip() for x in prev_entities if str(x).strip()]
        used_entities = bool(ingest.entities)

    should_carry_filters = _is_follow_up_query(ingest.raw_query) and not _is_generic_list_like(ingest.raw_query)
    if not ingest.request_filters and prev_filters and should_carry_filters:
        restored = []
        for f in prev_filters:
            if not isinstance(f, dict):
                continue
            field = str(f.get("field", "")).strip()
            op = str(f.get("op", "")).strip().lower()
            value = f.get("value")
            if field and op:
                restored.append(RequestFilter(field=field, op=op, value=value))
        ingest.request_filters = restored
        used_filters = bool(restored)
    elif not ingest.request_filters and _is_generic_list_like(ingest.raw_query):
        # Generic list requests should not inherit old restrictive filters.
        ingest.request_filters = []

    if str(ingest.intent).strip().lower() == "unknown":
        prev_intent = str(session_context.get("intent", "")).strip().lower()
        if prev_intent and prev_intent != "unknown":
            ingest.intent = prev_intent
            used_intent = True

    if used_entities and ingest.ambiguity_score > 0.3:
        ingest.ambiguity_score = round(max(0.15, ingest.ambiguity_score - 0.35), 4)
    if used_filters and ingest.ambiguity_score > 0.2:
        ingest.ambiguity_score = round(max(0.1, ingest.ambiguity_score - 0.25), 4)

    return ingest, {
        "used": bool(used_entities or used_filters or used_intent),
        "used_entities": used_entities,
        "used_filters": used_filters,
        "used_intent": used_intent,
    }


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

    ambiguity = float(ingest.get("ambiguity_score", 1.0) or 1.0)
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


def run_v2_pipeline(query: str, role: str = "DEFAULT", session_id: str = "", lang: str = "auto") -> dict:
    locale = _resolve_locale(query, lang=lang)
    ingest = ingest_query(query, role=role)
    session_context = get_session_context(session_id)
    ingest, context_usage = _apply_context_to_ingest(ingest, session_context)
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
        }

    plan = compile_execution_plan(ingest, reason_result)
    plan_validation = validate_execution_plan(plan)
    consistency = _validate_reasoning_consistency(
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
                },
                "reason": reason_result.get("planner_trace_v2", {}),
                "execute": {},
                "learn": {},
            },
            "planner_trace_v2": reason_result.get("planner_trace_v2", {}),
            "execution_trace": {},
            "result": [],
            "clarify_recommendation": _build_clarify_suggestion(
                {"entities": ingest.entities, "request_filters": [asdict(f) for f in ingest.request_filters]},
                {"guardrail": {"errors": plan_validation.errors}},
                locale=locale,
            ),
            "conversation_context": {
                "session_id": session_id,
                "used": context_usage,
                "saved": bool(saved_context),
            },
        }

    execution = execute_plan(plan)
    outcome = LessonOutcome(
        query=ingest.normalized_query,
        execution_plan=plan,
        success=execution.success,
        score_breakdown={},
        diagnostics={"execution_trace": execution.execution_trace},
    )
    learned = record_outcome(outcome)
    layer_ingest = {
        "intent": ingest.intent,
        "entities": ingest.entities,
        "ambiguity_score": ingest.ambiguity_score,
        "request_filters": [asdict(f) for f in ingest.request_filters],
        "context_usage": context_usage,
    }
    layer_reason = reason_result.get("planner_trace_v2", {})
    layer_execute = execution.execution_trace
    layer_learn = {
        "lesson_score_breakdown": learned.get("score_breakdown", {}),
        "success": execution.success,
    }
    runtime_sample = _build_runtime_learning_sample(
        query=ingest.normalized_query,
        layer_ingest=layer_ingest,
        plan=asdict(plan),
        success=execution.success,
    )
    evidence = _compute_learning_evidence(layer_ingest, execution.execution_trace)
    before_eval = evaluate_matrix_v2()
    if evidence.get("eligible"):
        appended_sample = append_trainset_sample(runtime_sample)
    else:
        appended_sample = {
            "status": "skipped",
            "reason": "insufficient_learning_evidence",
            "evidence": evidence,
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
        "evidence": evidence,
        "eval_before": before_eval,
        "train_artifact_version": train_artifact.get("version"),
        "eval_snapshot": eval_report,
    }
    learning_check = _build_learning_check(
        before_eval=before_eval,
        after_eval=eval_report,
        learning_update=learning_update,
        execution_success=execution.success,
    )
    recommendation = ""
    if not execution.success:
        recommendation = _build_clarify_suggestion(layer_ingest, execution.execution_trace, locale=locale)
    assistant_response = _build_professional_response(
        ingest.normalized_query,
        execution.data,
        execution.execution_trace,
        locale=locale,
    )
    learning_summary = _build_learning_summary(learning_update, locale=locale)
    saved_context = update_session_context(session_id, ingest, execution_plan=asdict(plan))

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
        "planner_trace_v2": reason_result.get("planner_trace_v2", {}),
        "execution_plan": asdict(plan),
        "execution_trace": execution.execution_trace,
        "result": execution.data,
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
    }
