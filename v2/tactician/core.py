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
    exact_match = bool(row_count == 1)

    if exact_match:
        if role == "SENIOR":
            recommended_next_steps = [
                "Đối chiếu owner, stage và trạng thái để xác nhận record này là nguồn sự thật.",
                "Mở rộng truy vấn quan hệ (contact/contract/opportunity) quanh đúng identity hiện tại.",
                "Nếu chuẩn bị hành động, chốt field mục tiêu rồi gửi lệnh update theo từng bước.",
            ]
            message_templates = [
                "Đã khóa đúng 1 bản ghi. Tôi sẽ mở rộng theo quan hệ liên quan thay vì lọc lại.",
                "Khuyến nghị tiếp theo: kiểm tra owner/stage/status trước khi thao tác cập nhật.",
            ]
        else:
            recommended_next_steps = [
                "Kiểm tra nhanh owner, trạng thái và trường liên hệ để xác nhận đúng hồ sơ.",
                "Yêu cầu xem thêm dữ liệu liên quan như contact/contract của đúng bản ghi này.",
                "Nếu cần cập nhật, nêu rõ field cần sửa và giá trị mới để hệ thống thực thi an toàn.",
            ]
            message_templates = [
                "Mình đã tìm đúng 1 bản ghi, giờ có thể đi sâu các trường liên quan.",
                "Bạn muốn mình mở rộng sang contact, contract hay opportunity liên quan?",
            ]
    elif role == "JUNIOR":
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
    elif exact_match:
        probe_questions = [
            "Bạn muốn soi sâu nhóm nào trước: thông tin liên hệ, owner hay trạng thái?",
            "Bạn có muốn lấy thêm dữ liệu liên quan quanh bản ghi này không?",
        ]

    return {
        "persona_context": persona_context,
        "recommended_next_steps": recommended_next_steps,
        "message_templates": message_templates,
        "probe_questions": probe_questions,
        "signals": {
            "row_count": row_count,
            "stalled": stalled,
            "exact_match": exact_match,
            "query": str(query or "").strip(),
        },
    }
