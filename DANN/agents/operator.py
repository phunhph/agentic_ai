from core.database import SessionLocal
from models.domain import Opportunity

class OperatorAgent: 
    def process_update(self, data):
        db = SessionLocal()
        try:
            # Ghi dữ liệu vào bảng hbl_opportunities theo cấu hình dự án
            new_opp = Opportunity(
                hbl_opportunities_name=data.get('name', 'Unnamed Deal'),
                hbl_opportunities_estimated_value=data.get('budget'),
                mixs=data.get('mixs', {}) # Lưu thông tin BANT vào mixs
            )
            db.add(new_opp)
            db.commit()
            return True
        except Exception as e:
            print(f"Lỗi DB: {e}")
            db.rollback()
            return False
        finally:
            db.close()