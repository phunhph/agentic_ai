"""
api/routes_events.py
Routes cho event pub/sub lifecycle.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException
from infra.settings import get_env_int

from pipeline.phase1_ingest.pubsub_ingress import publish_event
from pipeline.phase1_ingest.pubsub_worker import process_event
from v2.lifecycle import LIFECYCLE_STORE

router = APIRouter()

EVENT_ACK_SLA_MS = get_env_int("EVENT_ACK_SLA_MS", 1500)


@router.post("/api/v2/events/publish")
async def publish_v2_event(
    background_tasks: BackgroundTasks,
    goal: str = Form(...),
    role: str = Form("DEFAULT"),
    session_id: str = Form(""),
    lang: str = Form("auto"),
    source: str = Form("pubsub"),
):
    payload = {
        "goal": goal,
        "role": role,
        "session_id": session_id,
        "lang": lang,
        "source": source,
    }
    event = publish_event(payload, ack_sla_ms=EVENT_ACK_SLA_MS)
    event_id = str(event.get("event_id", ""))
    background_tasks.add_task(process_event, event_id, goal, role, session_id, lang)
    return {"ok": True, "event": event}


@router.get("/api/v2/events/{event_id}")
async def get_v2_event(event_id: str):
    state = LIFECYCLE_STORE.get(event_id)
    if not state:
        raise HTTPException(status_code=404, detail="event_not_found")
    return {"ok": True, "event": state}
