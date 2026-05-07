from v2.intelligence.resolver import DynamicIntentResolver
from core.contracts import RequestFilter


def _apply_context_to_ingest(ingest, session_context: dict) -> tuple[object, dict]:
    if not session_context:
        return ingest, {"used": False, "source": "none"}
    
    prev_entities = session_context.get("entities", []) if isinstance(session_context.get("entities"), list) else []
    prev_filters = session_context.get("request_filters", []) if isinstance(session_context.get("request_filters"), list) else []
    
    # Sử dụng Resolver Dynamic (thay vì list từ khóa cứng)
    is_follow_up = DynamicIntentResolver.is_follow_up(ingest.raw_query, session_context) > 0.5
    is_generic_list = DynamicIntentResolver.is_generic_list(ingest.raw_query) > 0.5

    used_entities = False
    used_filters = False
    used_intent = False
    reordered_entities = False

    # ... [Logic kế thừa giữ nguyên cấu trúc nhưng dùng biến mới] ...
    has_current_entities = bool(ingest.entities)
    
    if not has_current_entities and prev_entities:
        ingest.entities = [str(x).strip() for x in prev_entities if str(x).strip()]
        used_entities = bool(ingest.entities)
    
    prev_root = str(session_context.get("root_table", "")).strip()
    if (
        prev_root
        and ingest.entities
        and prev_root in ingest.entities
        and (is_follow_up or not has_current_entities)
    ):
        ingest.entities = [prev_root] + [e for e in ingest.entities if e != prev_root]
        reordered_entities = True
        used_entities = True

    should_carry_filters = (is_follow_up or not has_current_entities) and not is_generic_list
    if not ingest.request_filters and prev_filters and should_carry_filters:
        # ... logic khôi phục filter cũ ...
        restored = []
        for f in prev_filters:
            if not isinstance(f, dict): continue
            field = str(f.get("field", "")).strip()
            op = str(f.get("op", "")).strip().lower()
            value = f.get("value")
            if field and op:
                restored.append(RequestFilter(field=field, op=op, value=value))
        ingest.request_filters = restored
        used_filters = bool(restored)

    return ingest, {
        "used": bool(used_entities or used_filters or used_intent),
        "used_entities": used_entities,
        "used_filters": used_filters,
        "used_intent": used_intent,
        "reordered_entities": reordered_entities,
    }

apply_context_to_ingest = _apply_context_to_ingest
