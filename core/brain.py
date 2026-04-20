from core.memory import LongTermMemory

memory = LongTermMemory()

def call_brain_with_learning(state: dict):
    goal = state["goal"]
    
    # Lấy "kinh nghiệm" từ quá khứ
    past_experience = memory.get_advice(goal)
    
    prompt = f"""
    Mục tiêu: {goal}
    Kinh nghiệm quá khứ: {past_experience}
    Hãy suy luận bước tiếp theo...
    """
    # Gọi LLM xử lý...