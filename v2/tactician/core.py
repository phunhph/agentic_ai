from __future__ import annotations

from typing import Any


def build_tactician_payload(
    query: str,
    persona_context: dict,
    rows: list[dict[str, Any]],
    execution_trace: dict[str, Any],
) -> dict:
    role = str((persona_context or {}).get("role", "DEFAULT")).upper()
    row_count = int((execution_trace or {}).get("row_count", len(rows)) or len(rows))
    stalled = bool(row_count == 0)

    if role == "JUNIOR":
        recommended_next_steps = [
            "Xác nhận lại đúng đối tượng bằng tên đầy đủ hoặc mã định danh.",
            "Giữ 1 điều kiện lọc chính trước, sau đó mới thêm điều kiện phụ.",
            "Chạy lại truy vấn và kiểm tra tối đa 3 kết quả đầu tiên.",
        ]
        message_templates = [
            "Cho mình xin xác nhận tên đầy đủ của đối tượng để kiểm tra chính xác.",
            "Mình sẽ lọc theo 1 điều kiện chính trước để tránh lệch dữ liệu.",
        ]
    elif role == "SENIOR":
        recommended_next_steps = [
            "Khóa identity signal (name/code) trước khi mở rộng tiêu chí liên quan.",
            "Đối chiếu kết quả theo root entity hiện hành để tránh drift cross-table.",
            "Nếu dữ liệu rỗng, ưu tiên kiểm tra quality của filter trước khi đổi root.",
        ]
        message_templates = [
            "Proposed approach: freeze identity filter first, then expand relationship filters.",
            "I suggest validating root-entity alignment before broadening retrieval scope.",
        ]
    else:
        recommended_next_steps = [
            "Xác định rõ đối tượng chính bằng tên hoặc mã.",
            "Thêm điều kiện lọc cụ thể để tăng độ chính xác.",
        ]
        message_templates = [
            "Vui lòng cung cấp thêm định danh để truy vấn chính xác hơn.",
        ]

    probe_questions = []
    if stalled:
        probe_questions = [
            "Bạn muốn lọc theo tên đầy đủ hay theo mã định danh?",
            "Có cần mở rộng phạm vi thời gian hoặc trạng thái không?",
        ]

    return {
        "persona_context": persona_context,
        "recommended_next_steps": recommended_next_steps,
        "message_templates": message_templates,
        "probe_questions": probe_questions,
        "signals": {"row_count": row_count, "stalled": stalled, "query": str(query or "").strip()},
    }
