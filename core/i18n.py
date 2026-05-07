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
        "clarify_ambiguity_gate": "Yêu cầu đang bị đánh giá nhập nhằng cao. Hãy nêu rõ thực thể chính và 1 điều kiện định danh (ví dụ: tên account đầy đủ hoặc mã).",
        "clarify_no_rows": "Không có bản ghi khớp điều kiện hiện tại. Bạn có thể mở rộng filter hoặc đổi root entity.",
        "learn_not_updated": "Học tập: không cập nhật tri thức mới ({reason}).",
        "learn_updated": "Học tập: đã cập nhật ({mode}). Signature: {signature}",
        "learn_mode_new": "học mới một mẫu tri thức chưa từng có",
        "learn_mode_expand": "học bổ sung tri thức mới trong cùng nhóm intent",
        "learn_mode_contradiction": "học điều chỉnh cho signature đã có kết quả khác",
        "assistant_clarify": "Để đảm bảo độ chính xác, yêu cầu hiện tại cần được làm rõ trước khi thực thi. Vui lòng bổ sung đối tượng chính và điều kiện lọc cụ thể.",
        "assistant_untrusted": "Hệ thống tạm thời chưa thực thi vì đánh giá tin cậy chưa đạt ngưỡng an toàn. Vui lòng bổ sung thông tin để tăng độ chắc chắn của suy luận.",
        "update_success": "✅ **Thành công:** Dữ liệu BANT đã được cập nhật vào hệ thống CRM.",
        "update_fail": "❌ **Thất bại:** Không tìm thấy bản ghi phù hợp để thực hiện cập nhật.",
        "tactical_overview": "📊 **Phân tích chiến thuật:** Tìm thấy {count} kết quả phù hợp với tiêu chí của bạn.",
        "no_data_recommendation": "Không tìm thấy bản ghi nào thuộc thực thể **{root}** khớp với điều kiện hiện tại. Bạn có thể bổ sung tiêu chí cụ thể hơn (tên, mã) hoặc thử truy vấn danh sách tổng quát.",
        "junior_prefix": "💡 **Gợi ý:** ",
        "senior_prefix": "🚀 **Chiến lược:** ",
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
        "no_data_recommendation": "No records found for entity **{root}** matching your filters. Try adding more specific criteria or query a generic list.",
        "clarify_entities": "Please provide a specific target entity (account/contact/contract/opportunity).",
        "clarify_filters": "Please add filtering conditions (name, code, owner, date range) for a precise query.",
        "clarify_guardrail": "The plan is blocked by guardrails. Please adjust fields/filters to valid schema columns.",
        "clarify_ambiguity_gate": "The request is considered highly ambiguous. Please specify the primary entity and one identifying condition (for example full account name or code).",
        "clarify_no_rows": "No records match the current conditions. You can broaden filters or change the root entity.",
        "learn_not_updated": "Learning: no new knowledge update ({reason}).",
        "learn_updated": "Learning: updated ({mode}). Signature: {signature}",
        "learn_mode_new": "learned a brand new knowledge pattern",
        "learn_mode_expand": "expanded knowledge within the same intent group",
        "learn_mode_contradiction": "updated an existing signature with a different outcome",
        "assistant_clarify": "To ensure accuracy, this request needs clarification before execution. Please provide the primary target and specific filtering conditions.",
        "assistant_untrusted": "Execution is temporarily blocked because the trust score is below the safe threshold. Please provide more details to increase reasoning confidence.",
        "update_success": "✅ **Success:** BANT data has been successfully updated in the CRM.",
        "update_fail": "❌ **Failed:** No matching records found for the update request.",
        "tactical_overview": "📊 **Tactical Overview:** Found {count} results matching your criteria.",
        "junior_prefix": "💡 **Tip:** ",
        "senior_prefix": "🚀 **Insights:** ",
    }
    return (en if locale == "en" else vi).get(key, key)
