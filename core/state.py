from typing import List, Dict, Any, TypedDict

class AgentState(TypedDict):
    goal: str                # Yêu cầu của Phú
    role: str                # ADMIN/BUYER
    current_plan: List[str]  # Kế hoạch AI lập ra
    steps: List[Dict]        # Thought -> Action -> Observation
    is_finished: bool        # Trạng thái kết thúc
    final_output: Any        # Kết quả trả về giao diện