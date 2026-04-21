import re
import ollama
from infra.settings import OLLAMA_CHAT_MODEL


def semantic_router(goal: str, role: str):

    # 1. Kiểm tra an toàn thô (Security Guard)
    blacklist = ["drop table", "delete from", "truncate"]
    if any(word in goal.lower() for word in blacklist) and role != "ADMIN":
        return "SECURITY_VIOLATION"

    # 2. Định tuyến bằng LLM
    prompt = f"""
    Câu hỏi: "{goal}"
    Nhiệm vụ:
    1. Domain: INVENTORY, SALES, hoặc ACCOUNTING.
    2. Task Type: QUERY (Tìm kiếm), STATS (Thống kê), hay ACTION (Thay đổi dữ liệu).
    3. Keywords: Các danh từ/động từ quan trọng liên quan đến Database.

    Trả về JSON: {{"domain": "...", "task": "...", "keywords": [...]}}
    """
    response = ollama.generate(
        model=OLLAMA_CHAT_MODEL, prompt=prompt, options={"temperature": 0}
    )
    return response["response"]
