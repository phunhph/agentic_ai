import json
import ollama
import math
import hashlib
from pathlib import Path
from infra.settings import (
    OLLAMA_EMBEDDING_MODEL,
    RAG_EMBEDDING_CACHE_PATH,
    RAG_FORCE_REBUILD,
)


class MetadataRAG:
    def __init__(self):
        # Kho tri thức về Schema
        self.schema_kb = {
            "hbl_account": "Tài khoản khách hàng doanh nghiệp: hbl_accountid, hbl_account_name, thông tin website/domain/budget. Quan hệ lookup đến systemuser.",
            "hbl_contact": "Liên hệ khách hàng: hbl_contactid, hbl_contact_name, hbl_contact_accountid, mc_contact_assigneeid, email/phone. Quan hệ cha-con với hbl_account.",
            "hbl_opportunities": "Cơ hội bán hàng: hbl_opportunitiesid, hbl_opportunities_name, hbl_opportunities_accountid, owner, BANT. Quan hệ với account và contract.",
            "hbl_contract": "Hợp đồng: hbl_contractid, hbl_contract_name, hbl_contract_opportunityid, mc_contract_assigneeid, doanh thu theo tháng. Quan hệ với opportunities.",
            "systemuser": "Người dùng hệ thống (sales/owner/assignee): systemuserid, fullname, email. Được tham chiếu bởi account/contact/opportunities/contract.",
            "choice_option": "Bảng lựa chọn chuẩn: choice_optionid, choice_group, choice_code, choice_label. Dùng qua các bảng join n-n cho industry/status/month...",
            "choice_links": "Các bảng bắc cầu n-n: hbl_account_industry_choice, hbl_contact_source_choice_map, hbl_contract_status_choice_map, ...",
        }
        self.model = OLLAMA_EMBEDDING_MODEL
        self.embeddings = {}
        self._cache_path = Path(RAG_EMBEDDING_CACHE_PATH)
        self._load_or_initialize_embeddings()

    def _get_embedding(self, text):
        """Gọi Ollama để lấy vector embedding"""
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            return response["embedding"]
        except Exception as e:
            print(f"Lỗi lấy embedding: {e}")
            return None

    def _schema_signature(self) -> str:
        # Use a stable digest so cache remains reusable across process restarts.
        items = [self.model, *[f"{k}:{v}" for k, v in sorted(self.schema_kb.items())]]
        raw = "|".join(items).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _load_cached_embeddings(self) -> bool:
        if RAG_FORCE_REBUILD or not self._cache_path.exists():
            return False
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if payload.get("model") != self.model:
                return False
            if payload.get("schema_signature") != self._schema_signature():
                return False
            vectors = payload.get("embeddings")
            if not isinstance(vectors, dict) or not vectors:
                return False
            self.embeddings = vectors
            return True
        except Exception:
            return False

    def _save_cached_embeddings(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "model": self.model,
                "schema_signature": self._schema_signature(),
                "embeddings": self.embeddings,
            }
            self._cache_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            # Cache lỗi không chặn runtime.
            pass

    def _initialize_embeddings(self):
        """Khởi tạo vector cho các Schema."""
        print("Dang khoi tao tri thuc Schema (Vectorizing)...")
        for key, text in self.schema_kb.items():
            vector = self._get_embedding(text)
            if vector:
                self.embeddings[key] = vector
        self._save_cached_embeddings()

    def _load_or_initialize_embeddings(self):
        if self._load_cached_embeddings():
            print("Da nap tri thuc Schema tu cache.")
            return
        self._initialize_embeddings()

    def _cosine_similarity(self, v1, v2):
        """Tính độ tương đồng Cosine giữa 2 vector"""
        if not v1 or not v2:
            return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    def get_relevant_schema(self, query: str):
        """MÁY HỌC: Tìm kiếm ngữ nghĩa bằng Vector Embedding để lọc Schema"""
        query_vector = self._get_embedding(query)
        if not query_vector:
            return "General store information."

        # Tính điểm tương đồng cho từng bảng
        scores = []
        for key, vector in self.embeddings.items():
            score = self._cosine_similarity(query_vector, vector)
            scores.append((score, self.schema_kb[key]))

        # Sắp xếp và lấy các bảng có điểm cao nhất (> 0.4)
        relevant = [text for score, text in sorted(scores, reverse=True) if score > 0.4]

        # Nếu không có cái nào đạt ngưỡng, lấy cái cao nhất
        if not relevant and scores:
            relevant = [sorted(scores, reverse=True)[0][1]]

        return "\n".join(relevant[:2])  # Trả về tối đa 2 bảng liên quan nhất
