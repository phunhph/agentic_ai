# agents/analyst.py
from core.database import SessionLocal
from models.domain import Account

class AnalystAgent:
    def get_account_list(self):
        db = SessionLocal()
        try:
            # Lấy dữ liệu từ bảng hbl_account trong dbfi.json
            accounts = db.query(Account).all()
            if not accounts:
                return "Hiện chưa có account nào trong hệ thống."
            
            # Tạo chuỗi văn bản sạch[cite: 3]
            res = "Danh sách Account hiện tại:\n"
            for acc in accounts:
                res += f"• {acc.hbl_account_name}\n"
            return res
        finally:
            db.close()