import uuid


def normalize_role(role: str | None) -> str:
    return "DEFAULT"


def ensure_context_id(value: str | None) -> str:
    if value and str(value).strip():
        return str(value).strip()
    return str(uuid.uuid4())


def build_context_key(session_id: str, role: str, conversation_id: str) -> str:
    normalized_role = normalize_role(role)
    return f"{normalized_role}:{session_id}:{conversation_id}"
