"""
NeuralBrain — Bộ não DANN.
Thực hiện suy luận 1 lần duy nhất (single-pass) với Chain-of-Thought nội tại.
Output: JSON chứa cả plan lẫn conclusion bằng tiếng Việt.

Tối ưu latency:
  1. Activation Cache — query tương tự trả kết quả ngay, không gọi LLM
  2. Lean Prompt      — giảm input tokens để LLM xử lý nhanh hơn
  3. num_predict=150  — output JSON chỉ ~80 tokens, không cần 400
  4. Schema trimming  — chỉ gửi entity names + top fields, bỏ full dump
"""
import json
import hashlib
import logging
import datetime
import time
from collections import OrderedDict

from infra.settings import OLLAMA_REASONING_MODEL
import ollama

logger = logging.getLogger(__name__)


class NeuralBrain:
    # Cache tối đa 128 activation gần nhất (LRU)
    _CACHE_MAX = 128

    def __init__(self, model: str = OLLAMA_REASONING_MODEL):
        self.model = model
        self._cache: OrderedDict[str, dict] = OrderedDict()

    # ── Cache helpers ──────────────────────────────────────

    def _cache_key(self, query: str, schema_graph: dict) -> str:
        """Hash query + entity names → cache key. Bỏ qua weights vì chúng thay đổi liên tục."""
        entities = sorted(schema_graph.get("entities", {}).keys())
        raw = f"{query}||{'|'.join(entities)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_get(self, key: str) -> dict | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, key: str, value: dict):
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._CACHE_MAX:
            self._cache.popitem(last=False)

    # ── Trim schema cho prompt ─────────────────────────────

    @staticmethod
    def _trim_schema(schema_graph: dict) -> str:
        """Chỉ gửi entity names + top 5 fields → giảm tokens đáng kể."""
        entities = schema_graph.get("entities", {})
        if not entities:
            return "{}"
        trimmed = {}
        for name, info in entities.items():
            fields = info.get("fields", [])[:5]
            trimmed[name] = fields
        return json.dumps(trimmed, ensure_ascii=False)

    # ── Core activation ────────────────────────────────────

    def activate(self, query: str, schema_graph: dict, weights: dict) -> dict:
        """
        Single-pass DANN Activation.
        Input: query + weighted schema + historical weights.
        Output: {primary_entity, filters, intent, thought, conclusion_template}
        """
        # 1. Check cache trước
        cache_key = self._cache_key(query, schema_graph)
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug(f"[NeuralBrain] Cache HIT for query: {query[:50]}")
            return cached

        # 2. Build lean prompt
        now = datetime.datetime.now().strftime("%Y-%m-%d")

        top_paths = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
        exp = ", ".join(f"{k}({v:.1f})" for k, v in top_paths) if top_paths else "none"

        schema_str = self._trim_schema(schema_graph)

        # If schema_graph provides identity fields, add guidance to prefer them
        identity_guidance = ""
        try:
            id_parts = []
            for en, info in (schema_graph.get("entities") or {}).items():
                if info and info.get("identity_field"):
                    id_parts.append(f"{en}.{info.get('identity_field')}")
            if id_parts:
                identity_guidance = (
                    "\nNOTE: If the user requests information about a person or salesperson, "
                    "prefer filters on identity fields: " + ", ".join(id_parts) + "."
                )
        except Exception:
            identity_guidance = ""

        prompt = (
            f"""[DANN {now}]
SCHEMA: {schema_str}
EXP: {exp}
Q: {query}

Chọn bảng, trích filter, viết kết luận tiếng Việt (dùng {{count}} cho số lượng)."""
        ) + identity_guidance + (
            f"\n\nJSON: {{\"primary_entity\":\"tên_bảng\",\"intent\":\"retrieve|analyze\",\"filters\":[{{\"field\":\"cột\",\"op\":\"eq|contains\",\"value\":\"giá_trị\"}}],\"thought\":\"giải thích\",\"conclusion_template\":\"Dạ, Cindy... {{count}}...\"}}"
        )

        # 3. Call LLM
        t0 = time.time()
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                format="json",
                stream=False,
                options={
                    "num_predict": 1024,   # Tăng limit để chứa nội dung <think> của deepseek
                    "temperature": 0.1,
                    "num_ctx": 2048,      # Giới hạn context window → xử lý nhanh hơn
                },
            )
            elapsed = time.time() - t0
            logger.debug(f"[NeuralBrain] LLM call took {elapsed:.1f}s")

            response_text = response["response"]
            # Debug log raw model output for troubleshooting ambiguous selections
            logger.debug(f"[NeuralBrain] raw_response: {response_text[:200]!r}")
            
            # Xử lý output của DeepSeek (loại bỏ block <think>)
            import re
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
            
            # Cố gắng trích xuất JSON nếu model bọc trong ```json
            if '```json' in response_text:
                json_match = re.search(r'```json(.*?)```', response_text, flags=re.DOTALL)
                if json_match:
                    response_text = json_match.group(1).strip()
            elif '```' in response_text:
                json_match = re.search(r'```(.*?)```', response_text, flags=re.DOTALL)
                if json_match:
                    response_text = json_match.group(1).strip()

            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"[NeuralBrain] Lỗi parse JSON: {e}\nRaw text: {response_text}")
                # Fallback an toàn nếu parse lỗi
                result = {
                    "primary_entity": list(schema_graph.get("entities", {}).keys())[0] if schema_graph.get("entities") else "hbl_account",
                    "intent": "retrieve",
                    "filters": [],
                    "thought": "Lỗi parse JSON, dùng default",
                    "conclusion_template": "Dạ, Cindy gặp chút sự cố khi phân tích yêu cầu."
                }

            # Validation: đảm bảo primary_entity tồn tại trong schema
            entities = schema_graph.get("entities", {})
            logger.debug(f"[NeuralBrain] parsed_result={result} schema_entities={list(entities.keys())}")
            if result.get("primary_entity") not in entities and entities:
                result["primary_entity"] = list(entities.keys())[0]

            # Cache kết quả thành công
            self._cache_put(cache_key, result)

            return result
        except Exception as e:
            logger.warning(f"[NeuralBrain] LLM error after {time.time() - t0:.1f}s: {e}")
            return {
                "primary_entity": "hbl_account",
                "intent": "retrieve",
                "filters": [],
                "thought": f"Lỗi kích hoạt nơ-ron: {str(e)}",
                "conclusion_template": "Xin lỗi, Cindy gặp sự cố khi xử lý yêu cầu.",
            }
