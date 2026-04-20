from tools.inventory_tool import search_products, get_inventory_stats
from tools.order_tool import get_orders, get_order_details
from core.learning import AgentLearning

learning = AgentLearning()

# Dynamic Tool Registry - dễ dàng thêm tool mới
TOOL_REGISTRY = {
    "search_products": {
        "func": search_products,
        "extract_args": lambda args: [args.get("keyword", "")],
        "description": "Tìm kiếm sản phẩm theo từ khóa"
    },
    "get_inventory_stats": {
        "func": get_inventory_stats,
        "extract_args": lambda args: [],
        "description": "Thống kê tồn kho theo danh mục"
    },
    "get_orders": {
        "func": get_orders,
        "extract_args": lambda args: [args.get("customer_name")],
        "description": "Lấy danh sách đơn hàng"
    },
    "get_order_details": {
        "func": get_order_details,
        "extract_args": lambda args: [args.get("order_id")],
        "description": "Lấy chi tiết đơn hàng theo ID"
    },
}

def action_node(state: dict):
    tool = state.get("next_action")
    args = state.get("next_args", {})
    goal = state.get("goal")
    
    observation = []
    
    if tool in TOOL_REGISTRY:
        try:
            tool_info = TOOL_REGISTRY[tool]
            func_args = tool_info["extract_args"](args)
            observation = tool_info["func"](*func_args)
        except Exception as e:
            observation = []
            log = {
                "block": "ACT",
                "content": f"Lỗi khi gọi {tool}: {str(e)}",
                "status": "ERROR"
            }
            return {"observations": observation, "node_logs": [log]}
    elif tool == "final_answer":
        # Giữ nguyên observations cũ
        observation = state.get("observations", [])
    else:
        log = {
            "block": "ACT",
            "content": f"Tool '{tool}' không tồn tại. Tools có sẵn: {list(TOOL_REGISTRY.keys())}",
            "status": "UNKNOWN_TOOL"
        }
        return {"observations": [], "node_logs": [log]}
    
    # TẦNG HỌC HỎI: Ghi lại kết quả để AI tự rút kinh nghiệm
    success = len(observation) > 0
    learning.record_lesson(goal, tool, success)
    
    log = {
        "block": "ACT",
        "content": f"Đã gọi {tool}. Tìm thấy {len(observation)} bản ghi.",
        "status": "SUCCESS" if success else "NOT_FOUND"
    }
    
    return {
        "observations": observation,
        "node_logs": [log]
    }