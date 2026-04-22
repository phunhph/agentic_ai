from __future__ import annotations

import re

_NON_WORD = re.compile(
    r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]"
)


def clean_goal_text(text: str) -> str:
    """Giữ nguyên hoa/thường, chỉ loại ký tự không phải chữ/số/khoảng trắng."""
    return " ".join(_NON_WORD.sub(" ", text or "").split())


def normalize_goal_text(text: str) -> str:
    """Lowercase + chuẩn hóa khoảng trắng (dùng cho so khớp intent / alias)."""
    return " ".join(_NON_WORD.sub(" ", (text or "").lower()).split())
