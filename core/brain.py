import ollama
import json
from core.vector_store import MetadataRAG
from core.learning import AgentLearning
from core.settings import OLLAMA_CHAT_MODEL

rag = MetadataRAG()
learning = AgentLearning()

def agent_brain(state: dict):
    # 1. ROUTER & KNOWLEDGE: Lấy mảnh Schema liên quan
    relevant_schema = rag.get_relevant_schema(state["goal"])

    # 2. LEARNING: Lấy kinh nghiệm từ quá khứ
    past_experience = learning.recall_memory(state["goal"])

    # 3. CONTEXT: Lấy observations và history
    previous_obs = state.get("observations", [])
    obs_context = json.dumps(previous_obs, ensure_ascii=False) if previous_obs else "Chưa có dữ liệu."

    history = state.get("history", [])
    history_context = "\n".join([f"User: {h['goal']}\nAssistant: {h['result']}" for h in history[-3:]]) if history else "Không có lịch sử hội thoại."

    # 4. REASONING: Llama 3 suy luận
    prompt = f"""
    [SYSTEM] Bạn là Agent điều hành kho thông minh Enterprise. Trả lời bằng JSON duy nhất.
    [SCHEMA] {relevant_schema}
    [EXPERIENCE] {past_experience}
    [CHAT HISTORY] {history_context}
    [PREVIOUS OBS] {obs_context}
    [USER GOAL] {state['goal']}
    [ITERATION] {state.get('iteration', 1)}/5

    Nhiệm vụ: Phân tích mục tiêu và chọn công cụ phù hợp.
    Tools có sẵn:
    - search_products: tìm sản phẩm (keyword)
    - get_inventory_stats: thống kê tồn kho ()
    - get_orders: danh sách đơn hàng (customer_name)
    - get_order_details: chi tiết đơn hàng (order_id)
    - final_answer: khi đã có đủ dữ liệu ()

    Format JSON: {{"thought": "suy nghĩ", "tool": "tên_tool", "args": {{...}}}}
    """

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = ollama.generate(model=OLLAMA_CHAT_MODEL, prompt=prompt, format='json')
            result = json.loads(response['response'])

            # Validation
            if "tool" not in result: result["tool"] = "search_products"
            if "args" not in result: result["args"] = {}
            if "thought" not in result: result["thought"] = "..."

            return result
        except Exception:
            if attempt < max_retries: continue
            return {"thought": "Lỗi xử lý. Thử tìm kiếm.", "tool": "search_products", "args": {"keyword": state["goal"]}}
