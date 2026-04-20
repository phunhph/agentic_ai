import json
import ollama
import math

class MetadataRAG:
    def __init__(self):
        # Kho tri thức về Schema
        self.schema_kb = {
            "products": "Thông tin sản phẩm: name, price, sku, category_id, base_price. Mối quan hệ với categories.id. Dùng khi hỏi về hàng hóa, giá cả.",
            "inventories": "Thông tin kho: quantity, location, product_id, warehouse_location. Mối quan hệ với products.id. Dùng khi hỏi về số lượng tồn kho, vị trí kho.",
            "categories": "Danh mục: name, description. Dùng khi phân loại sản phẩm, tra cứu nhóm hàng.",
            "orders": "Đơn hàng: id, customer_id, status, total_price. Quan hệ: customers.id. Dùng khi tra cứu lịch sử mua bán, trạng thái đơn hàng.",
            "customers": "Khách hàng: id, name, email, address. Dùng khi tìm kiếm thông tin khách hàng.",
            "order_items": "Chi tiết đơn hàng: id, order_id, product_id, quantity, price_at_order. Dùng khi xem chi tiết các món trong đơn."
        }
        self.model = "llama3:latest"
        self.embeddings = {}
        self._initialize_embeddings()

    def _get_embedding(self, text):
        """Gọi Ollama để lấy vector embedding"""
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            return response["embedding"]
        except Exception as e:
            print(f"Lỗi lấy embedding: {e}")
            return None

    def _initialize_embeddings(self):
        """Khởi tạo vector cho các Schema (Trong thực tế nên cache vào file/DB)"""
        print("🚀 Đang khởi tạo tri thức Schema (Vectorizing)...")
        for key, text in self.schema_kb.items():
            vector = self._get_embedding(text)
            if vector:
                self.embeddings[key] = vector

    def _cosine_similarity(self, v1, v2):
        """Tính độ tương đồng Cosine giữa 2 vector"""
        if not v1 or not v2: return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        if magnitude1 == 0 or magnitude2 == 0: return 0.0
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

        return "\n".join(relevant[:2]) # Trả về tối đa 2 bảng liên quan nhất