import requests

class RouterAgent:
    def __init__(self, model="llama3:8b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def classify(self, text: str) -> str:
        prompt = f"""
        Phân loại ý định tin nhắn CRM sau vào 1 trong 3 loại: 
        1. UPDATE (nếu muốn thêm/sửa dữ liệu)
        2. QUERY (nếu muốn hỏi/tìm kiếm dữ liệu)
        3. HELP (các yêu cầu khác)
        
        Tin nhắn: "{text}"
        Trả về DUY NHẤT từ khóa loại.
        """
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        try:
            response = requests.post(self.url, json=payload, timeout=5)
            return response.json().get("response", "HELP").strip().upper()
        except Exception:
            # Fallback heuristic: simple keyword matching
            t = text.lower()
            if any(w in t for w in ("cập nhật", "update", "tạo", "ghi" ,"tạo tài khoản", "tạo tài")):
                return "UPDATE"
            if any(w in t for w in ("tìm", "kiểm tra", "thống kê", "thống kê", "thế có")):
                return "QUERY"
            return "HELP"