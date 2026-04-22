"""Trích entity từ goal dựa hoàn toàn vào Metadata và tri thức hệ thống."""

from __future__ import annotations
import re
from functools import lru_cache
from typing import Any
from core.metadata_provider import get_metadata_provider
from dynamic_metadata.text_normalize import normalize_goal_text
from storage.database import SessionLocal
from storage.models import SystemUser

_USER_FIELD_PATTERNS = [
    ("bd_owner_id", re.compile(r"\b(?:bd|business development)\s*(?:la|là|=|is)?\s*([a-z0-9][a-z0-9\s\-_]{1,80})$", re.IGNORECASE)),
    ("am_sales_id", re.compile(r"\b(?:am|account manager)\s*(?:la|là|=|is)?\s*([a-z0-9][a-z0-9\s\-_]{1,80})$", re.IGNORECASE)),
]


def _find_system_user_id(display_name: str) -> tuple[str | None, str | None, float]:
    name_norm = normalize_goal_text(display_name)
    if not name_norm:
        return None, None, 0.0
    users = _load_system_users()
    best_id = None
    best_name = None
    best_score = 0.0
    target_tokens = set(name_norm.split())
    for uid, fullname in users:
        f = str(fullname or "").strip()
        fn = normalize_goal_text(f)
        if not fn:
            continue
        if fn == name_norm:
            return str(uid), f, 1.0
        f_tokens = set(fn.split())
        inter = len(target_tokens.intersection(f_tokens))
        union = len(target_tokens.union(f_tokens)) or 1
        score = inter / union
        if score > best_score:
            best_score = score
            best_id = str(uid)
            best_name = f
    if best_score >= 0.55:
        return best_id, best_name, best_score
    return None, None, 0.0


@lru_cache(maxsize=1)
def _load_system_users() -> tuple[tuple[str, str], ...]:
    db = SessionLocal()
    try:
        rows = db.query(SystemUser.systemuserid, SystemUser.fullname).all()
    finally:
        db.close()
    return tuple((str(uid), str(fullname or "")) for uid, fullname in rows)

def extract_entities(goal: str) -> dict[str, Any]:
    # 1. Chuẩn hóa text (Chỉ xử lý format, không lọc từ lóng ở đây)
    normalized = normalize_goal_text(goal)
    tokens = normalized.split()
    provider = get_metadata_provider()

    # 2. Nhận diện Bảng (Hoàn toàn dựa vào Alias trong db.json)
    mentioned_tables: list[str] = []
    for gram_len in (2, 1):
        for i in range(0, len(tokens) - gram_len + 1):
            gram = " ".join(tokens[i : i + gram_len])
            table = provider.resolve_alias(gram)
            if table and table not in mentioned_tables:
                mentioned_tables.append(table)

    # 3. Nhận diện Choice (Duyệt động từ Provider)
    choices: list[dict[str, str]] = []
    # Dùng set để lưu các token đã xác định là Choice/Table nhằm lọc keyword sau này
    known_tokens = set()

    # Truy cập schema động từ provider
    for group, options in provider._schema.choice_options.items():
        for option in options:
            label = str(option.get("label", "")).strip()
            normalized_label = normalize_goal_text(label)
            # So khớp label trong chuỗi đã chuẩn hóa
            if normalized_label and f" {normalized_label} " in f" {normalized} ":
                choices.append({
                    "group": group, 
                    "label": label,
                    "code": option.get("code")
                })
                # Đánh dấu các từ này đã "có danh phận" trong DB
                known_tokens.update(normalized_label.split())

    # 4. Keyword Extraction (Cơ chế Loại trừ tri thức)
    # Thay vì liệt kê NOISE_TOKENS, ta loại bỏ:
    # - Các từ đã được resolve thành Table
    # - Các từ đã được resolve thành Choice
    # Những gì còn lại sẽ được đưa cho LLM ở bước sau để tự lọc nhiễu ngữ nghĩa
    
    keyword_tokens = []
    for t in tokens:
        if provider.resolve_alias(t): continue
        if t in known_tokens: continue
        keyword_tokens.append(t)

    keyword = " ".join(keyword_tokens).strip()

    identities: list[dict[str, Any]] = []
    extracted_entities: dict[str, Any] = {}
    for field_name, pattern in _USER_FIELD_PATTERNS:
        m = pattern.search(normalized)
        if not m:
            continue
        raw_name = m.group(1).strip()
        user_id, canonical_name, confidence = _find_system_user_id(raw_name)
        if not user_id:
            continue
        identities.append(
            {
                "type": "systemuser",
                "id": user_id,
                "name": canonical_name,
                "field": field_name,
                "confidence": confidence,
            }
        )
        extracted_entities[field_name] = user_id
        extracted_entities[field_name.replace("_id", "_name")] = canonical_name

    return {
        "normalized_goal": normalized,
        "mentioned_tables": mentioned_tables,
        "choices": choices,
        "keyword": keyword,
        "identities": identities,
        "extracted_entities": extracted_entities,
    }