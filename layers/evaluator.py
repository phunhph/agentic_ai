def evaluator_node(state: dict):
    observations = state.get("observations", [])
    iteration = state.get("iteration", 0)
    
    # Nếu có dữ liệu trả về -> Kết thúc thành công
    if observations:
        return {"is_finished": True, "status": "GOAL_REACHED"}
    
    # Nếu sau 3 lần thử mà vẫn rỗng -> Dừng lại báo lỗi để tránh Loop vô tận
    if iteration >= 3:
        return {
            "is_finished": True, 
            "node_logs": [{"block": "EVAL", "content": "Đã thử nhiều cách nhưng không tìm thấy dữ liệu phù hợp.", "status": "FAILED"}]
        }
    
    # Nếu chưa có kết quả, trả về False để Brain tiếp tục suy luận hướng khác
    return {"is_finished": False}