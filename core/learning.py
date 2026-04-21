import json
import os
import ollama
import math
from core.settings import OLLAMA_EMBEDDING_MODEL

class AgentLearning:
    def __init__(self):
        self.path = "logs/learning_data.json"
        self.model = OLLAMA_EMBEDDING_MODEL
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def _get_embedding(self, text):
        """Lấy vector embedding từ Ollama"""
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            return response["embedding"]
        except Exception:
            return None

    def _cosine_similarity(self, v1, v2):
        if not v1 or not v2: return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        if magnitude1 == 0 or magnitude2 == 0: return 0.0
        return dot_product / (magnitude1 * magnitude2)

    def add_experience(self, goal, tool_used, success):
        """Lưu trải nghiệm và vector hóa goal để tìm kiếm sau này"""
        vector = self._get_embedding(goal)
        with open(self.path, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data.append({
                "goal": goal,
                "tool": tool_used,
                "success": success,
                "vector": vector
            })
            f.seek(0)
            f.truncate()
            json.dump(data[-50:], f, ensure_ascii=False, indent=2)

    def record_lesson(self, goal, tool, success):
        self.add_experience(goal, tool, success)

    def recall_memory(self, goal):
        """MÁY HỌC: Tìm các bài học trong quá khứ có nội dung tương tự bằng Vector"""
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data:
                return "Hệ thống chưa có kinh nghiệm thực tế."

            query_vector = self._get_embedding(goal)
            if not query_vector:
                return "Không thể phân tích ngữ nghĩa yêu cầu."

            # Tìm case có độ tương đồng cao nhất và thành công
            best_match = None
            max_score = -1.0

            for entry in data:
                if not entry.get("success") or "vector" not in entry or not entry["vector"]:
                    continue

                score = self._cosine_similarity(query_vector, entry["vector"])
                if score > max_score and score > 0.7: # Ngưỡng tin cậy 0.7
                    max_score = score
                    best_match = entry

            if best_match:
                return f"BÀI HỌC ML: Với yêu cầu tương tự '{best_match['goal']}' (độ khớp {int(max_score*100)}%), tool '{best_match['tool']}' đã thành công."

            return "Chưa tìm thấy bài học tương tự chặt chẽ trong quá khứ."
        except Exception as e:
            return f"Lỗi truy xuất bộ nhớ: {str(e)}"

    def get_lesson(self, goal):
        return self.recall_memory(goal)
