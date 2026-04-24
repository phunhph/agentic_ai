from __future__ import annotations

import json
import re
import time
from pathlib import Path
from threading import Lock

from v2.contracts import IngestResult

_SESSION_TTL_SECONDS = 60 * 30
_MAX_SESSIONS = 300
_STORE_PATH = Path("storage/v2/context/session_contexts.json")

_LOCK = Lock()
_SESSIONS: dict[str, dict] = {}
_LOADED = False


def _ensure_loaded_locked():
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    if not _STORE_PATH.exists():
        return
    try:
        raw = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(raw, dict):
        return
    for sid, ctx in raw.items():
        if isinstance(sid, str) and isinstance(ctx, dict):
            _SESSIONS[sid] = dict(ctx)


def _persist_locked():
    try:
        _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(_SESSIONS, ensure_ascii=False, indent=2)
        _STORE_PATH.write_text(payload, encoding="utf-8")
    except Exception:
        # Persist failure should not break runtime flow.
        return


def _compact() -> bool:
    changed = False
    now = time.time()
    expired = [sid for sid, data in _SESSIONS.items() if now - float(data.get("ts", now)) > _SESSION_TTL_SECONDS]
    for sid in expired:
        if sid in _SESSIONS:
            _SESSIONS.pop(sid, None)
            changed = True
    if len(_SESSIONS) <= _MAX_SESSIONS:
        return changed
    by_oldest = sorted(_SESSIONS.items(), key=lambda x: float(x[1].get("ts", now)))
    for sid, _ in by_oldest[: len(_SESSIONS) - _MAX_SESSIONS]:
        if sid in _SESSIONS:
            _SESSIONS.pop(sid, None)
            changed = True
    return changed


def get_session_context(session_id: str) -> dict:
    sid = str(session_id or "").strip()
    if not sid:
        return {}
    with _LOCK:
        _ensure_loaded_locked()
        if _compact():
            _persist_locked()
        return dict(_SESSIONS.get(sid, {}))


def list_session_contexts(limit: int = 100) -> list[dict]:
    with _LOCK:
        _ensure_loaded_locked()
        changed = _compact()
        rows: list[dict] = []
        for sid, ctx in _SESSIONS.items():
            ts = float(ctx.get("ts", 0.0) or 0.0)
            rows.append(
                {
                    "session_id": sid,
                    "ts": ts,
                    "intent": str(ctx.get("intent", "")).strip(),
                    "entities": ctx.get("entities", []) if isinstance(ctx.get("entities"), list) else [],
                    "root_table": str(ctx.get("root_table", "")).strip(),
                    "last_query": str(ctx.get("last_query", "")).strip(),
                }
            )
        rows.sort(key=lambda x: float(x.get("ts", 0.0)), reverse=True)
        if changed:
            _persist_locked()
        limit = max(1, min(int(limit or 100), 500))
        return rows[:limit]


def create_session_context(session_id: str) -> dict:
    sid = str(session_id or "").strip()
    if not sid:
        return {}
    now = time.time()
    context = {
        "ts": now,
        "intent": "",
        "entities": [],
        "request_filters": [],
        "root_table": "",
        "join_path": [],
        "last_query": "",
        "last_normalized_query": "",
    }
    with _LOCK:
        _ensure_loaded_locked()
        _compact()
        _SESSIONS[sid] = context
        _persist_locked()
        return {"session_id": sid, **context}


def update_session_context(session_id: str, ingest: IngestResult, execution_plan: dict | None = None) -> dict:
    sid = str(session_id or "").strip()
    if not sid:
        return {}
    def _mask_query(text: str) -> str:
        out = re.sub(r"\b\d+\b", "<num>", str(text or "").strip())
        out = re.sub(r"\"[^\"]+\"|'[^']+'", "<text>", out)
        return out

    def _redact_filters(rows: list) -> list[dict]:
        out: list[dict] = []
        for f in rows or []:
            if not hasattr(f, "field"):
                continue
            out.append({"field": str(getattr(f, "field", "")).strip(), "op": str(getattr(f, "op", "")).strip(), "value": "<redacted>"})
        return out

    context = {
        "ts": time.time(),
        "intent": str(ingest.intent or "").strip(),
        "entities": list(ingest.entities or []),
        "request_filters": _redact_filters(list(ingest.request_filters or [])),
    }
    if isinstance(execution_plan, dict):
        context["root_table"] = str(execution_plan.get("root_table", "")).strip()
        context["join_path"] = execution_plan.get("join_path", []) if isinstance(execution_plan.get("join_path"), list) else []
    context["last_query"] = _mask_query(str(ingest.raw_query or "").strip())
    context["last_normalized_query"] = _mask_query(str(ingest.normalized_query or "").strip())
    with _LOCK:
        _ensure_loaded_locked()
        _compact()
        _SESSIONS[sid] = context
        _persist_locked()
        return dict(context)
