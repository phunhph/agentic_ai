"""Bước perception LLM: phân loại intent + entity từ goal dựa trên tri thức động."""

from __future__ import annotations
import json
import re
import ollama
from agent.field_resolver import INTENT_TOOL_HINT
from infra.settings import OLLAMA_CHAT_MODEL
from dynamic_metadata.trace_metrics import estimate_tokens

# Pattern ID vẫn giữ Regex vì đây là định dạng kỹ thuật cố định
_ORDER_ID_PATTERN = re.compile(r"\b(?:dh|don|order)?[-_\s]?(\d{3,})\b", re.IGNORECASE)

def llm_parse_intent_entities(goal: str, normalized_goal: str) -> tuple[str, dict, dict]:
    allowed_intents = sorted([*INTENT_TOOL_HINT.keys(), "UNKNOWN"])
    
    # 2. Xây dựng Prompt động dựa trên Metadata thực tế
    prompt = f"""
Bạn là bộ phân tích ý định CRM chuyên nghiệp. 
Dựa vào Schema và Tools hiện có, hãy phân tích yêu cầu của người dùng.

DANH SÁCH INTENT CHO PHÉP:
{", ".join(allowed_intents)}

SCHEMA TRẢ VỀ (JSON):
{{
  "intent": "Tên intent khớp với danh sách trên",
  "entities": {{
    "keyword": "tên riêng, từ khóa tìm kiếm",
    "contract_id": "ID hợp đồng nếu có",
    "status": "trạng thái nếu có",
    "customer_name": "tên khách hàng"
  }}
}}

QUY TẮC:
- Chỉ sử dụng Intent có trong danh sách. Nếu không khớp, trả về UNKNOWN.
- Loại bỏ mọi từ ngữ nhiễu, từ lóng trong quá trình trích xuất entities.
- Nếu người dùng nhắc đến một đối tượng không có trong Metadata, trả về UNKNOWN.
- Nếu intent là CONTACT_LIST và câu có dạng "contact của account X" thì điền entities.customer_name = X.

User goal gốc: {goal}
User goal chuẩn hóa: {normalized_goal}
""".strip()

    # 3. Gọi LLM và xử lý kết quả
    response = ollama.generate(model=OLLAMA_CHAT_MODEL, prompt=prompt, format="json")
    raw = json.loads(response["response"])
    
    intent = str(raw.get("intent", "UNKNOWN")).strip().upper()
    
    # Validation động: Kiểm tra lại với tri thức Metadata
    if intent not in allowed_intents:
        intent = "UNKNOWN"
        
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    io_trace = {
        "intent_parser_input": {
            "goal": goal,
            "normalized_goal": normalized_goal,
            "allowed_intents": allowed_intents,
            "prompt_tokens_est": estimate_tokens(prompt),
        },
        "intent_parser_output": {
            "intent": intent,
            "entities": entities,
            "response_tokens_est": estimate_tokens(raw),
        },
    }
    return intent, entities, io_trace

def extract_order_contract_id(normalized_goal: str) -> str | None:
    """Trích xuất ID kỹ thuật bằng Regex."""
    m = _ORDER_ID_PATTERN.search(normalized_goal)
    return m.group(1) if m else None