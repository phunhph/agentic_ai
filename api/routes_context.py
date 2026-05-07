"""
api/routes_context.py
Routes cho session context management.
"""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException

from memory.session import (
    clear_all_session_contexts,
    create_session_context,
    delete_session_context,
    list_session_contexts,
)

router = APIRouter()


@router.get("/api/v2/contexts")
async def list_v2_contexts(limit: int = 100):
    try:
        items = list_session_contexts(limit=limit)
        return {"ok": True, "contexts": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v2/contexts")
async def create_v2_context(session_id: str = Form(...)):
    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        row = create_session_context(sid)
        return {"ok": True, "context": row}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/v2/contexts/{session_id}")
async def delete_v2_context(session_id: str):
    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        removed = delete_session_context(sid)
        return {"ok": True, "deleted": bool(removed), "session_id": sid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/v2/contexts")
async def clear_v2_contexts():
    try:
        deleted_count = clear_all_session_contexts()
        return {"ok": True, "deleted_count": int(deleted_count)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
