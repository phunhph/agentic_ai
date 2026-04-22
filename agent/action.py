from memory.learning import AgentLearning
from infra.policy import is_tool_allowed
from tools.tool_registry import TOOL_REGISTRY, build_call_args

learning = AgentLearning()


def _sanitize_observation(tool: str, observation):
    tool_info = TOOL_REGISTRY.get(tool, {})
    allowed_fields = tool_info.get("output_fields")
    if not isinstance(allowed_fields, list) or not allowed_fields:
        return observation, 0
    allowed = set(allowed_fields)
    dropped = 0

    def _clean_item(item):
        nonlocal dropped
        if not isinstance(item, dict):
            return item
        cleaned = {}
        for k, v in item.items():
            if k in allowed:
                cleaned[k] = v
            else:
                dropped += 1
        return cleaned

    if isinstance(observation, list):
        return [_clean_item(x) for x in observation], dropped
    if isinstance(observation, dict):
        return _clean_item(observation), dropped
    return observation, 0


def action_node(state: dict):
    tool = state.get("next_action")
    args = state.get("next_args", {})
    goal = state.get("goal")
    role = state.get("role", "DEFAULT")
    domain = state.get("domain", "general")
    request_contract = state.get("request_contract", {})

    observation = []

    allowed, deny_reason = is_tool_allowed(role, tool)
    if not allowed:
        log = {
            "block": "POLICY",
            "content": deny_reason,
            "status": "DENIED",
        }
        return {"observations": [], "node_logs": [log]}

    # Guardrail: chỉ cho execute nếu contract request hợp lệ
    if request_contract and not request_contract.get("valid", True):
        log = {
            "block": "POLICY",
            "content": f"Request contract invalid: {request_contract.get('reason', 'unknown')}",
            "status": "BLOCKED",
        }
        return {"observations": [], "node_logs": [log]}

    if tool in TOOL_REGISTRY:
        try:
            tool_info = TOOL_REGISTRY[tool]
            func_args = build_call_args(tool, args)
            observation = tool_info["func"](*func_args)
            observation, dropped_fields = _sanitize_observation(tool, observation)
        except Exception as e:
            observation = []
            dropped_fields = 0
            log = {
                "block": "ACT",
                "content": f"Lỗi khi gọi {tool}: {str(e)}",
                "status": "ERROR",
            }
            return {"observations": observation, "node_logs": [log]}
    elif tool == "final_answer":
        observation = state.get("observations", [])
        dropped_fields = 0
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
    sanitize_log = {
        "block": "POLICY",
        "content": f"Output sanitize: dropped_fields={dropped_fields}",
        "status": "ENFORCED",
    }
    learning_log = {
        "block": "LEARN",
        "content": f"Đã ghi lesson ({str(role).upper()} / {domain}) cho tool '{tool}' với trạng thái {'SUCCESS' if success else 'NOT_FOUND'}.",
        "status": "RECORDED",
    }

    return {
        "observations": observation,
        "node_logs": [action_log, sanitize_log, learning_log],
    }
