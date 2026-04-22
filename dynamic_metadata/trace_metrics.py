from __future__ import annotations

import json
from typing import Any


def estimate_tokens(value: Any) -> int:
    """Approximate token count without external tokenizer dependency."""
    if value is None:
        return 0
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    return max(1, len(text) // 4) if text else 0

