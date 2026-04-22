def evaluator_node(state: dict):
    observations = state.get("observations", [])
    iteration = state.get("iteration", 0)
    selected_tool = str(state.get("selected_tool", "")).strip()

    # Nếu có dữ liệu trả về -> Kết thúc thành công
    if observations:
        return {
            "is_finished": True,
            "status": "GOAL_REACHED",
            "node_logs": [{"block": "EVAL", "content": "Đủ dữ liệu, kết thúc vòng lặp.", "status": "DONE"}]
        }

    # Nếu sau 3 lần thử mà vẫn rỗng -> Dừng lại báo lỗi để tránh Loop vô tận
    if iteration >= 3:
        return {
            "is_finished": True,
            "node_logs": [{"block": "EVAL", "content": "Đã thử nhiều cách nhưng không tìm thấy dữ liệu phù hợp.", "status": "FAILED"}]
        }

    # Tối ưu độ trễ: với các tool list/read chuẩn, nếu vòng đầu đã rỗng thì dừng sớm.
    # Tránh lặp 2-3 vòng reason/act không tạo thêm tín hiệu mới.
    if iteration >= 1 and selected_tool in {
        "list_accounts",
        "list_contacts",
        "list_contracts",
        "list_opportunities",
        "get_contract_details",
    }:
        return {
            "is_finished": True,
            "status": "NO_DATA",
            "node_logs": [{"block": "EVAL", "content": "Không có dữ liệu phù hợp ở truy vấn hiện tại, dừng sớm để giảm độ trễ.", "status": "DONE"}]
        }

    # Nếu chưa có kết quả, trả về False để Brain tiếp tục suy luận hướng khác
    return {
        "is_finished": False,
        "status": "CONTINUE",
        "node_logs": [{"block": "EVAL", "content": "Chưa đủ dữ liệu, tiếp tục suy luận vòng sau.", "status": "RETRY"}]
    }
