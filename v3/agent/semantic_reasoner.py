from __future__ import annotations
import json
import ollama
from v2.metadata import MetadataProvider

class SemanticReasoner:
    """
    Stage 2: Core Reasoning & Planning with Self-Reflection.
    Sử dụng llama3:latest với một lượt gọi duy nhất để tối ưu tốc độ.
    """
    
    def __init__(self, model: str = "llama3:latest"):
        self.model = model
        self.provider = MetadataProvider()

    def reason(self, query: str) -> dict:
        schema_info = self._get_schema_summary(query)
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        prompt = f"""
Bạn là một Chuyên gia CRM Cao cấp. 
Thời gian hiện tại: {now}

CẤU TRÚC HỆ THỐNG:
{schema_info}

CÂU HỎI NGƯỜI DÙNG: {query}

HƯỚNG DẪN QUAN TRỌNG:
1. Intent: retrieve|analyze|create|update.
2. Quy tắc CRM:
   - "chăm sóc", "cần làm", "todo" -> Tìm trong bảng Tasks hoặc Opportunities. KHÔNG BAO GIỜ tìm các từ này trong trường 'name'.
   - "sales", "nhân viên", "user" -> LUÔN LUÔN sử dụng bảng 'systemuser'.
   - Chỉ lọc ngày tháng nếu có từ khóa rõ ràng như "hôm nay", "tuần này", "tháng 3".
   - Nếu không có yêu cầu lọc, hãy để danh sách "filters" trống.

3. PHẢN HỒI BẰNG TIẾNG VIỆT 100%:
   - Trả lời lịch sự, chuyên nghiệp.
   - Luôn giải thích suy luận (thought_process) bằng tiếng Việt.

ĐỊNH DẠNG ĐẦU RA (JSON DUY NHẤT):
{{
  "thought_process": "Giải thích suy luận của bạn bằng tiếng Việt",
  "intent": "retrieve",
  "primary_entity": "tên_bảng_chính",
  "entities": ["bảng1"],
  "filters": [
    {{"field": "bảng.trường", "op": "eq|contains", "value": "giá_trị"}}
  ],
  "sort": {{"field": "bảng.trường", "direction": "asc|desc"}},
  "aggregation": {{"type": "count|none", "field": "..."}},
  "confidence_score": 0.95,
  "suggested_response": "Lời chào chuyên nghiệp (Ví dụ: 'Dạ, đây là danh sách các đối tác mà bạn yêu cầu:')",
  "reflection": "Tự kiểm tra tính logic của kế hoạch",
  "final_decision": "ready|ask_clarify",
  "clarify_message": "Câu hỏi làm rõ nếu cần"
}}
"""
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                format="json",
                stream=False,
                options={"temperature": 0.0}
            )
            raw_content = response["response"]
            clean_content = raw_content.strip()
            if "```json" in clean_content:
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_content:
                clean_content = clean_content.split("```")[1].split("```")[0].strip()
                
            return json.loads(clean_content)
        except Exception as e:
            return {
                "error": str(e),
                "intent": "unknown",
                "final_decision": "ask_clarify",
                "clarify_message": f"Hệ thống gặp sự cố: {str(e)}"
            }

    def _get_schema_summary(self, query: str) -> str:
        summary = []
        core = ["hbl_account", "hbl_contact", "hbl_opportunities", "hbl_contract"]
        context_map = {
            "systemuser": ["sales", "user", "nhân viên", "người", "ai"],
            "task": ["nhiệm vụ", "công việc", "todo", "chăm sóc", "lịch"],
            "hbl_contract": ["hợp đồng", "contract"],
            "hbl_opportunities": ["cơ hội", "opp", "op"]
        }
        
        target_tables = set(core)
        q_lower = query.lower()
        for table, keywords in context_map.items():
            if any(k in q_lower for k in keywords):
                target_tables.add(table)

        for table in target_tables:
            fields = list(self.provider.get_identity_priority_fields(table))[:3]
            all_fields = self.provider.get_fields(table)
            for f in all_fields:
                if f not in fields and len(fields) < 5:
                    fields.append(f)
            summary.append(f"- {table}: {', '.join(fields)}")
        return "\n".join(summary)
