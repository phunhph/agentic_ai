import ollama
# Phú có thể dùng một thư viện máy học nhẹ như scikit-learn hoặc dùng chính LLM làm Router
def semantic_router(goal: str):
    # Đây là nơi máy học quyết định câu hỏi thuộc về Domain nào
    # Ví dụ: "Cắm trại" -> Domain: SALES, "Thống kê" -> Domain: ADMIN
    prompt = f"Phân loại domain cho: {goal}. Trả về 1 từ duy nhất: ADMIN, BUYER, SUPPORT."
    response = ollama.generate(model='gemma2:2b', prompt=prompt)
    return response['response'].strip()