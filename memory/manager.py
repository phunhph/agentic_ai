import hashlib
import json
import os
import ollama
import math
from datetime import datetime
from infra.settings import OLLAMA_EMBEDDING_MODEL


def _experience_path(context_key: str | None) -> str:
    """Một file JSON / context_key — không trộn kinh nghiệm giữa các phiên."""
    base = os.path.join("logs", "experience")
    os.makedirs(base, exist_ok=True)
    if not context_key or not str(context_key).strip():
        return os.path.join(base, "_default.json")
    digest = hashlib.sha256(str(context_key).encode("utf-8")).hexdigest()[:32]
    return os.path.join(base, f"{digest}.json")


class AgentMemory:
    def __init__(self, file_path: str | None = None):
        # Giữ tham số tương thích cũ; nếu truyền file_path thì dùng làm file duy nhất (legacy).
        self._legacy_file_path = file_path

    def _resolve_path(self, context_key: str | None) -> str:
        if self._legacy_file_path:
            return self._legacy_file_path
        return _experience_path(context_key)

    def _get_embedding(self, text):
        try:
            response = ollama.embeddings(model=OLLAMA_EMBEDDING_MODEL, prompt=text)
            return response["embedding"]
        except Exception:
            return None

    def _cosine_similarity(self, v1, v2):
        if not v1 or not v2:
            return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        return (
            dot_product / (magnitude1 * magnitude2)
            if magnitude1 * magnitude2 > 0
            else 0.0
        )

    def save_experience(
        self,
        goal: str,
        action: str,
        result_count: int,
        context_key: str | None = None,
    ):
        path = self._resolve_path(context_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        vector = self._get_embedding(goal)
        experience = {
            "goal": goal,
            "action": action,
            "success": result_count > 0,
            "timestamp": str(datetime.now()),
            "vector": vector,
            "context_key": context_key,
        }

        data = []
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = []

        data.append(experience)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data[-50:], f, ensure_ascii=False, indent=4)

    def get_advice(self, goal: str, context_key: str | None = None):
        """Tìm kinh nghiệm tương tự trong đúng ngữ cảnh (file) của context_key."""
        path = self._resolve_path(context_key)
        try:
            if not os.path.exists(path):
                return "Chưa có kinh nghiệm cũ cho ngữ cảnh này."

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            query_vector = self._get_embedding(goal)
            if not query_vector or not data:
                return "Hệ thống đang tích lũy kinh nghiệm."

            best_match = None
            max_score = -1.0

            for d in data:
                if d.get("success") and "vector" in d and d["vector"]:
                    score = self._cosine_similarity(query_vector, d["vector"])
                    if score > max_score:
                        max_score = score
                        best_match = d

            if best_match and max_score > 0.7:
                return (
                    f"Gợi ý ML: Với yêu cầu '{best_match['goal']}', "
                    f"hành động '{best_match['action']}' đã thành công."
                )

            return "Hãy thử phân tích các bảng dữ liệu liên quan."
        except Exception:
            return "Đã xảy ra lỗi khi truy xuất bộ nhớ."
