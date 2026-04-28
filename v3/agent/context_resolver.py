import ollama
from infra.settings import OLLAMA_REASONING_MODEL
from v3.agent.learning_analyst import LearningAnalyst

class ContextResolver:
    """
    Stage 1: Resolve conversation context and implicit references (pronouns, etc.)
    Uses llama3 for consistency with Stage 2.
    """
    
    def __init__(self, model: str = "llama3:latest"):
        self.model = model
        self.analyst = LearningAnalyst()

    def resolve(self, query: str, history: list[dict]) -> dict:
        # Fast Path: Check if history is empty or query has no pronouns
        pronouns = ["nó", "họ", "thằng", "con", "ấy", "đó", "ông", "bà", "anh", "chị"]
        q_lower = query.lower()
        has_pronoun = any(p in q_lower for p in pronouns)
        
        # Correction signals
        correction_keywords = ["không phải", "sai rồi", "nhầm rồi", "ý tôi là", "phải là"]
        is_correction = any(k in q_lower for k in correction_keywords)
        
        if not history or (not has_pronoun and not is_correction):
            return {"query": query, "is_correction": is_correction}
            
        # Format history for the prompt (last 3-5 turns)
        history_str = ""
        for turn in history[-5:]:
            role = "Người dùng" if turn.get("role") == "user" else "Trợ lý"
            content = turn.get("content", "")
            history_str += f"{role}: {content}\n"

        prompt = f"""
Bạn là chuyên gia Phân tích Ngữ cảnh cho hệ thống CRM.
Nhiệm vụ của bạn là viết lại Câu hỏi cuối cùng của Người dùng sao cho đầy đủ ý nghĩa bằng cách giải quyết các đại từ (nó, họ, anh ấy, dự án đó...) dựa trên lịch sử trò chuyện.

Quy tắc:
- Nếu câu hỏi đã rõ ràng, hãy giữ nguyên.
- KHÔNG trả lời câu hỏi. CHỈ viết lại câu hỏi.
- Giữ nguyên ngôn ngữ của người dùng.

Lịch sử trò chuyện:
{history_str}

Câu hỏi mới nhất: {query}

Câu hỏi sau khi viết lại đầy đủ:"""

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                stream=False,
                options={"temperature": 0.0}
            )
            resolved_query = response["response"].strip()
            return {
                "query": resolved_query if resolved_query else query,
                "is_correction": is_correction
            }
        except Exception:
            return {"query": query, "is_correction": is_correction}
