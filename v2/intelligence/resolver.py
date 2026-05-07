"""
v2/intelligence/resolver.py
Dynamic Intent Resolver sử dụng Neural Matrix.
"""
from intelligence.neural_matrix import NeuralMatrix

matrix = NeuralMatrix()

class DynamicIntentResolver:
    @staticmethod
    def is_follow_up(query: str, session_context: dict) -> float:
        """
        Dùng DANN để dự đoán xác suất query này là follow-up của phiên cũ.
        """
        # Sử dụng Neural Matrix để tìm các query tương tự đã được đánh dấu là follow-up
        results = matrix.find_similar(query, threshold=0.7)
        if not results:
            return 0.0
        # Nếu top kết quả có success cao, ta tin là follow-up
        return float(results[0]["similarity"])

    @staticmethod
    def is_generic_list(query: str) -> float:
        # Tương tự cho list request
        results = matrix.find_similar(query, threshold=0.8)
        if results and results[0]["sample"].get("intent") == "retrieve":
            return 0.9
        return 0.1
