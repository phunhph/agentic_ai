from __future__ import annotations
import ollama
from infra.settings import OLLAMA_REASONING_MODEL

class ResponseArchitect:
    """
    Stage 3: Build a professional, helpful response based on data and reasoning.
    Uses a fast model to ensure assistant-like tone.
    """
    def __init__(self, model: str = OLLAMA_REASONING_MODEL):
        self.model = model

    def build_response(self, query: str, data: list, reasoning: dict) -> str:
        if not data:
            return "Dạ, tôi đã kiểm tra hệ thống nhưng rất tiếc là chưa tìm thấy dữ liệu nào phù hợp với yêu cầu của bạn. Bạn có muốn tôi tìm kiếm theo tiêu chí khác không?"
            
        count = len(data)
        thought = reasoning.get("thought_process", "")
        
        prompt = f"""
You are a helpful and professional Sales Assistant. 
The user asked: "{query}"
The system found {count} records.
Internal reasoning: {thought}

Task: Write a polite, professional response in Vietnamese to the user.
- If there are many records (e.g. > 10), summarize and ask if they want to see details.
- If there are few, list the main highlights.
- Be supportive and clear.

Assistant Response:"""

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                stream=False,
                options={"temperature": 0.7}
            )
            return response["response"].strip()
        except Exception:
            return f"Dạ, tôi đã tìm thấy {count} kết quả cho bạn. Bạn có muốn xem chi tiết không?"
