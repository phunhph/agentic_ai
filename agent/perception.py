import re


def perception_node(state: dict):
    goal = state.get("goal", "")
    requested_role = str(state.get("role", "BUYER")).strip().upper()
    requested_role = requested_role if requested_role in {"ADMIN", "BUYER"} else "BUYER"

    # Chuẩn hóa text (giữ tiếng Việt có dấu)
    clean_goal = re.sub(
        r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
        " ",
        goal,
    )
    clean_goal = " ".join(clean_goal.split())

    # Ưu tiên role do UI gửi (ADMIN / BUYER), không đoán lại từ nội dung.
    role = requested_role

    return {
        "goal": clean_goal,
        "role": role,
        "status": "NORMALIZED",
    }
