import re

def perception_node(state: dict):
    goal = state.get("goal", "")
    # Xóa khoảng trắng thừa và ký tự đặc biệt gây nhiễu LLM
    clean_goal = re.sub(r'[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', ' ', goal)
    clean_goal = " ".join(clean_goal.split())

    # Xác định Role sơ bộ dựa trên từ khóa (Phú có thể để AI làm ở Brain)
    role = "ADMIN" if any(word in clean_goal.lower() for word in ["thống kê", "báo cáo", "tồn kho"]) else "BUYER"

    return {
        "goal": clean_goal,
        "role": role,
        "status": "NORMALIZED"
    }
