"""
phase6_respond/builder.py
Tách từ v2/service.py — build deterministic professional response (không dùng LLM).
"""
from __future__ import annotations

from core.i18n import _t
from core.formatting import _format_value, _humanize_field_key


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


def _is_detail_intent_query(query: str) -> bool:
    lowered = str(query or "").lower()
    detail_tokens = ["chi tiết", "chi tiet", "thông tin", "thong tin", "detail", "details"]
    return any(token in lowered for token in detail_tokens)


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
    return merged[:6]


def build_professional_response(
    query: str,
    rows: list[dict],
    execution_trace: dict,
    locale: str = "vi",
) -> str:
    """
    Build deterministic professional response dựa trên dữ liệu.
    Không dùng LLM — đây là fallback an toàn.
    """
    plan = execution_trace.get("plan", {})
    if plan and plan.get("update_data"):
        if execution_trace.get("updated_count", 0) > 0:
            return _t(locale, "update_success")
        return _t(locale, "update_fail")

    if not rows:
        root_table = str((execution_trace.get("plan", {}) or {}).get("root_table", "entity")).replace("hbl_", "")
        recommendation = _t(locale, "no_data_recommendation").format(root=root_table)
        if locale == "en":
            return f"⚠️ **No matching results.** {recommendation}\n\nTry narrowing by a specific name/code or date range."
        return f"⚠️ **Không có kết quả khớp.** {recommendation}\n\nBạn có thể thử thêm tên/mã cụ thể hoặc khoảng thời gian."

    overview = _t(locale, "tactical_overview").format(count=len(rows))
    root_table = str((execution_trace.get("plan", {}) or {}).get("root_table", "")).replace("hbl_", "").strip()
    preview_lines: list[str] = []
    detail_mode = _is_detail_intent_query(query)
    max_fields = 5 if len(rows) == 1 and detail_mode else (4 if len(rows) == 1 else 2)
    for idx, row in enumerate(rows[:3], start=1):
        if not isinstance(row, dict):
            continue
        fields = _pick_presentable_fields(row, root_table=f"hbl_{root_table}" if root_table else "")
        if not fields:
            continue
        label = " / ".join(f"{_humanize_field_key(k, locale)}: {_format_value(v)}" for k, v in fields[:max_fields])
        preview_lines.append(f"- {idx}. {label}")

    if locale == "en":
        details = "\n".join(preview_lines) if preview_lines else "- No concise preview available."
        hidden = max(0, len(rows) - len(preview_lines))
        hidden_line = f"\n- +{hidden} more rows available." if hidden > 0 else ""
        if len(rows) == 1:
            return (
                "✅ **Found exactly one matching record.**\n\n"
                f"Key details:\n{details}\n\n"
                "You can continue with related data exploration (contacts/contracts/opportunities) "
                "or request a focused field group for verification."
            )
        return f"{overview}\n\nTop matches:\n{details}{hidden_line}\n\nSuggested next step: add one more filter to narrow to exact target."

    details = "\n".join(preview_lines) if preview_lines else "- Chưa tạo được tóm tắt ngắn cho bản ghi."
    hidden = max(0, len(rows) - len(preview_lines))
    hidden_line = f"\n- +{hidden} bản ghi khác chưa hiển thị." if hidden > 0 else ""
    if len(rows) == 1:
        return (
            "✅ **Đã tìm thấy đúng 1 bản ghi phù hợp.**\n\n"
            f"Chi tiết chính:\n{details}\n\n"
            "Bạn có thể khai thác tiếp dữ liệu liên quan (contact/contract/opportunity) "
            "hoặc yêu cầu nhóm trường cần kiểm tra sâu."
        )
    return f"{overview}\n\nKết quả nổi bật:\n{details}{hidden_line}\n\nGợi ý tiếp theo: thêm 1 điều kiện lọc để chốt đúng đối tượng cần xử lý."


def build_clarify_suggestion(ingest: dict, execution_trace: dict, locale: str = "vi") -> str:
    """Build gợi ý làm rõ khi pipeline không thực thi được."""
    consistency_issues = execution_trace.get("consistency_issues", [])
    if isinstance(consistency_issues, list) and "high_ambiguity_without_clarify" in consistency_issues:
        return _t(locale, "clarify_ambiguity_gate")
    if not ingest.get("entities"):
        return _t(locale, "clarify_entities")
    filters = ingest.get("request_filters", [])
    if not filters:
        return _t(locale, "clarify_filters")
    guardrail = execution_trace.get("guardrail", {})
    if isinstance(guardrail, dict) and guardrail.get("errors"):
        return _t(locale, "clarify_guardrail")
    return _t(locale, "clarify_no_rows")


def build_learning_summary(learning_update: dict, locale: str = "vi") -> str:
    """Build text mô tả kết quả learning update."""
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


# Aliases cho backwards compat
_build_professional_response = build_professional_response
_build_clarify_suggestion = build_clarify_suggestion
_build_learning_summary = build_learning_summary
