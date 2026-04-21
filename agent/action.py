from memory.learning import AgentLearning
from infra.policy import is_tool_allowed
from tools.tool_registry import TOOL_REGISTRY, build_call_args

learning = AgentLearning()


def action_node(state: dict):
    tool = state.get("next_action")
    args = state.get("next_args", {})
    goal = state.get("goal")
    role = state.get("role", "BUYER")
    domain = state.get("domain", "general")

    observation = []

    allowed, deny_reason = is_tool_allowed(role, tool)
    if not allowed:
        log = {
            "block": "POLICY",
            "content": deny_reason,
            "status": "DENIED",
        }
        return {"observations": [], "node_logs": [log]}

    if tool in TOOL_REGISTRY:
        try:
            tool_info = TOOL_REGISTRY[tool]
            func_args = build_call_args(tool, args)
            observation = tool_info["func"](*func_args)
        except Exception as e:
            observation = []
            log = {
                "block": "ACT",
                "content": f"Lỗi khi gọi {tool}: {str(e)}",
                "status": "ERROR",
            }
            return {"observations": observation, "node_logs": [log]}
    elif tool == "final_answer":
        observation = state.get("observations", [])
    else:
        log = {
            "block": "ACT",
            "content": f"Tool '{tool}' không tồn tại. Tools có sẵn: {list(TOOL_REGISTRY.keys())}",
            "status": "UNKNOWN_TOOL",
        }
        return {"observations": [], "node_logs": [log]}

    success = len(observation) > 0
    learning.record_lesson(goal, tool, success, role, domain)

    action_log = {
        "block": "ACT",
        "content": f"Đã gọi {tool}. Tìm thấy {len(observation)} bản ghi.",
        "status": "SUCCESS" if success else "NOT_FOUND",
    }
    learning_log = {
        "block": "LEARN",
        "content": f"Đã ghi lesson ({str(role).upper()} / {domain}) cho tool '{tool}' với trạng thái {'SUCCESS' if success else 'NOT_FOUND'}.",
        "status": "RECORDED",
    }

    return {
        "observations": observation,
        "node_logs": [action_log, learning_log],
    }
