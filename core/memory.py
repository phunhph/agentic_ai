import json
import os
from datetime import datetime

class LongTermMemory:
    def __init__(self, memory_file="logs/experience_base.json"):
        self.memory_file = memory_file
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, 'w') as f:
                json.dump([], f)

    def learn_from_experience(self, goal: str, steps: list, success: bool):
        """Học từ kết quả thực tế"""
        experience = {
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "best_tools": [s['action'] for s in steps if success],
            "failed_tools": [s['action'] for s in steps if not success],
            "success": success
        }
        
        with open(self.memory_file, 'r+') as f:
            data = json.load(f)
            data.append(experience)
            f.seek(0)
            json.dump(data[-100:], f, indent=4) # Lưu 100 trải nghiệm gần nhất

    def get_advice(self, current_goal: str):
        """Gợi ý cho Brain dựa trên quá khứ"""
        # Trong thực tế sẽ dùng Vector Search ở đây để tìm Goal tương tự
        return "Lần trước với mục tiêu này, bạn đã thành công khi dùng 'get_inventory_stats'."