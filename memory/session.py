"""
memory/session.py
Move từ v2/memory.py — session context management cho multi-turn conversations.
Re-export toàn bộ từ v2/memory để duy trì single source of truth.
"""
# Re-export from v2/memory.py — single source of truth, tránh duplicate code
from v2.memory import (
    get_session_context,
    update_session_context,
    list_session_contexts,
    create_session_context,
    delete_session_context,
    clear_all_session_contexts,
)

__all__ = [
    "get_session_context",
    "update_session_context",
    "list_session_contexts",
    "create_session_context",
    "delete_session_context",
    "clear_all_session_contexts",
]
