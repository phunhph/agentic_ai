import ollama
from core.settings import OLLAMA_CHAT_MODEL

def semantic_router(goal: str):
    """Máy học phân loại: Quyết định xem câu hỏi thuộc Domain nào"""
    prompt = f"""
    Dựa vào câu hỏi: "{goal}"
    Phân loại vào 1 trong các nhóm sau: INVENTORY_DOMAIN, SALES_DOMAIN, ACCOUNTING_HOME.
    Chỉ trả về TÊN NHÓM duy nhất.
    """
    response = ollama.generate(model=OLLAMA_CHAT_MODEL, prompt=prompt, options={'temperature': 0})
    domain = response['response'].strip()
    return domain if domain in ["INVENTORY_DOMAIN", "SALES_DOMAIN", "ACCOUNTING_HOME"] else "INVENTORY_DOMAIN"