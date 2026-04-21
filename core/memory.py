import json
import os
import ollama
import math
from datetime import datetime
from core.settings import OLLAMA_EMBEDDING_MODEL

class AgentMemory:
    def __init__(self, file_path="logs/experience.json"):
        self.file_path = file_path
        self.model = OLLAMA_EMBEDDING_MODEL
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def _get_embedding(self, text):
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
        return dot_product / (magnitude1 * magnitude2) if magnitude1 * magnitude2 > 0 else 0.0

    def save_experience(self, goal: str, action: str, result_count: int):
        vector = self._get_embedding(goal)
        experience = {
            "goal": goal,
            "action": action,
            "success": result_count > 0,
            "timestamp": str(datetime.now()),
            "vector": vector
        }
        
        data = []
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception: data = []
        
        data.append(experience)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data[-50:], f, ensure_ascii=False, indent=4)

    def get_advice(self, goal: str):
        """MÁY HỌC: Tìm kiếm kinh nghiệm tương tự bằng Vector Similarity"""
        try:
            if not os.path.exists(self.file_path):
                return "Chưa có kinh nghiệm cũ."
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            query_vector = self._get_embedding(goal)
            if not query_vector or not data: return "Hệ thống đang tích lũy kinh nghiệm."

            best_match = None
            max_score = -1.0
            
            for d in data:
                if d.get("success") and "vector" in d and d["vector"]:
                    score = self._cosine_similarity(query_vector, d["vector"])
                    if score > max_score:
                        max_score = score
                        best_match = d

            if best_match and max_score > 0.7:
                return f"Gợi ý ML: Với yêu cầu '{best_match['goal']}', hành động '{best_match['action']}' đã thành công."
            
            return "Hãy thử phân tích các bảng dữ liệu liên quan."
        except Exception:
            return "Đã xảy ra lỗi khi truy xuất bộ nhớ."