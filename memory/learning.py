import json
import os
import ollama
import math
from infra.settings import OLLAMA_EMBEDDING_MODEL
from infra.domain import normalize_domain_key


class AgentLearning:
    def __init__(self):
        self.base_dir = "logs"
        self.default_path = os.path.join(self.base_dir, "learning_data.json")
        self.model = OLLAMA_EMBEDDING_MODEL
        os.makedirs(self.base_dir, exist_ok=True)
        if not os.path.exists(self.default_path):
            with open(self.default_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _normalize_role(self, role: str | None) -> str:
        normalized = (role or "BUYER").strip().upper()
        return normalized if normalized in {"ADMIN", "BUYER"} else "BUYER"

    def _get_store_path(self, role: str | None, domain: str | None) -> str:
        normalized_role = self._normalize_role(role)
        d = normalize_domain_key(domain)
        role_path = os.path.join(
            self.base_dir,
            f"learning_data_{normalized_role.lower()}_{d}.json",
        )
        if not os.path.exists(role_path):
            with open(role_path, "w", encoding="utf-8") as f:
                json.dump([], f)
        return role_path

    def _get_embedding(self, text):
        """Lấy vector embedding từ Ollama"""
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            return response["embedding"]
        except Exception:
            return None

    def _cosine_similarity(self, v1, v2):
        if not v1 or not v2:
            return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    def add_experience(self, goal, tool_used, success, role="BUYER", domain="general"):
        """Lưu trải nghiệm và vector hóa goal để tìm kiếm sau này"""
        vector = self._get_embedding(goal)
        d = normalize_domain_key(domain)
        role_path = self._get_store_path(role, d)
        with open(role_path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.append(
                {
                    "goal": goal,
                    "tool": tool_used,
                    "success": success,
                    "vector": vector,
                    "role": self._normalize_role(role),
                    "domain": d,
                }
            )
            f.seek(0)
            f.truncate()
            json.dump(data[-50:], f, ensure_ascii=False, indent=2)

    def record_lesson(self, goal, tool, success, role="BUYER", domain="general"):
        self.add_experience(goal, tool, success, role, domain)

    def recall_memory(self, goal, role="BUYER", domain="general"):
        """MÁY HỌC: Tìm các bài học trong quá khứ có nội dung tương tự bằng Vector"""
        try:
            d = normalize_domain_key(domain)
            role_path = self._get_store_path(role, d)
            with open(role_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data:
                return f"Hệ thống chưa có kinh nghiệm thực tế cho role {self._normalize_role(role)} / domain {d}."

            query_vector = self._get_embedding(goal)
            if not query_vector:
                return "Không thể phân tích ngữ nghĩa yêu cầu."

            # Tìm case có độ tương đồng cao nhất và thành công
            best_match = None
            max_score = -1.0

            for entry in data:
                if (
                    not entry.get("success")
                    or "vector" not in entry
                    or not entry["vector"]
                ):
                    continue

                score = self._cosine_similarity(query_vector, entry["vector"])
                if score > max_score and score > 0.7:  # Ngưỡng tin cậy 0.7
                    max_score = score
                    best_match = entry

            if best_match:
                return f"BÀI HỌC ML ({self._normalize_role(role)} / {d}): Với yêu cầu tương tự '{best_match['goal']}' (độ khớp {int(max_score*100)}%), tool '{best_match['tool']}' đã thành công."

            return f"Chưa tìm thấy bài học tương tự chặt chẽ cho role {self._normalize_role(role)} / domain {d}."
        except Exception as e:
            return f"Lỗi truy xuất bộ nhớ: {str(e)}"

    def get_lesson(self, goal, role="BUYER", domain="general"):
        return self.recall_memory(goal, role, domain)
