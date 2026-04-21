import json
import re

import ollama

from agent.field_resolver import resolve_request
from infra.settings import OLLAMA_CHAT_MODEL


_TEXT_NORMALIZER_PATTERN = re.compile(
    r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]"
)
_ORDER_ID_PATTERN = re.compile(r"\b(?:dh|don|order)?[-_\s]?(\d{3,})\b", re.IGNORECASE)
_ALLOWED_INTENTS = {
    "SEARCH_PRODUCTS",
    "ORDER_LOOKUP",
    "ORDER_DETAILS",
    "INVENTORY_STATS",
    "UNKNOWN",
}


def _normalize_text(text: str) -> str:
    return " ".join(_TEXT_NORMALIZER_PATTERN.sub(" ", (text or "").lower()).split())


def _llm_parse_request(goal: str, normalized_goal: str) -> tuple[str, dict]:
    prompt = f"""
Bạn là bộ phân tích ý định user cho hệ thống bán hàng.
Trả về JSON duy nhất theo schema:
{{
  "intent": "SEARCH_PRODUCTS|ORDER_LOOKUP|ORDER_DETAILS|INVENTORY_STATS|UNKNOWN",
  "entities": {{
    "keyword": "string",
    "order_id": "string",
    "status": "string",
    "customer_name": "string"
  }}
}}

Quy tắc:
- Chỉ chọn intent trong danh sách cho phép.
- keyword phải ngắn gọn, bỏ từ đệm nếu user đang tìm/mua sản phẩm.
- Nếu không chắc thì intent=UNKNOWN.

User goal gốc: {goal}
User goal chuẩn hóa: {normalized_goal}
""".strip()

    response = ollama.generate(model=OLLAMA_CHAT_MODEL, prompt=prompt, format="json")
    raw = json.loads(response["response"])
    intent = str(raw.get("intent", "UNKNOWN")).strip().upper()
    if intent not in _ALLOWED_INTENTS:
        intent = "UNKNOWN"
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    return intent, entities


def perception_node(state: dict):
    goal = state.get("goal", "")
    requested_role = str(state.get("role", "BUYER")).strip().upper()
    requested_role = requested_role if requested_role in {"ADMIN", "BUYER"} else "BUYER"

    # Chuẩn hóa text (giữ tiếng Việt có dấu)
    clean_goal = " ".join(
        re.sub(
            r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
            " ",
            goal,
        ).split()
    )
    normalized_goal = _normalize_text(clean_goal)
    try:
        intent, entities = _llm_parse_request(clean_goal, normalized_goal)
    except Exception:
        intent = "UNKNOWN"
        entities = {}

    order_id_match = _ORDER_ID_PATTERN.search(normalized_goal)
    if order_id_match and not entities.get("order_id"):
        entities["order_id"] = order_id_match.group(1)

    keyword = str(entities.get("keyword", "")).strip()
    if intent == "SEARCH_PRODUCTS" and not keyword:
        keyword = normalized_goal
    entities["keyword"] = keyword
    normalized_request = resolve_request(intent, entities)

    # Ưu tiên role do UI gửi (ADMIN / BUYER), không đoán lại từ nội dung.
    role = requested_role

    planner_goal = keyword if intent == "SEARCH_PRODUCTS" and keyword else clean_goal

    return {
        "goal": clean_goal,
        "normalized_goal": normalized_goal,
        "planner_goal": planner_goal,
        "intent": intent,
        "entities": normalized_request.entities,
        "request_contract": normalized_request.model_dump(),
        "role": role,
        "status": "NORMALIZED",
    }
