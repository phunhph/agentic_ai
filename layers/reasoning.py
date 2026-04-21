import ollama
import json
from core.schema import get_relevant_schema
from layers.router import semantic_router
from core.settings import OLLAMA_REASONING_MODEL

def reasoning_node(state: dict):
    goal = state["goal"]

    # BƯỚC 1: MÁY HỌC ĐỊNH TUYẾN (Không gửi cả hệ thống lớn)
    domain = semantic_router(goal)

    # BƯỚC 2: TRUY XUẤT KIẾN THỨC (Chỉ lấy mảnh dữ liệu liên quan)
    relevant_metadata = get_relevant_schema(domain)

    # BƯỚC 3: SUY LUẬN (REASONING)
    prompt = f"""
    ROLE: Solution Architect Agent
    CONTEXT_SCHEMA: {json.dumps(relevant_metadata)}
    GOAL: {goal}

    Hãy suy nghĩ bước tiếp theo. Nếu cần dữ liệu, hãy chọn tool.
    Tools: [search_products, get_inventory_stats, final_answer]

    Format JSON: {{"thought": "...", "tool": "...", "args": {{...}}}}
    """

    response = ollama.generate(model=OLLAMA_REASONING_MODEL, prompt=prompt, format='json')
    decision = json.loads(response['response'])

    return {
        "thought": decision["thought"],
        "next_action": decision["tool"],
        "next_args": decision["args"],
        "node_logs": [{"block": "REASON", "content": decision["thought"], "status": "THINKING"}]
    }
