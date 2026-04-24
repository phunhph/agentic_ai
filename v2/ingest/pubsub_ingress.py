from __future__ import annotations

from typing import Any

from v2.lifecycle import LIFECYCLE_STORE


def publish_event(payload: dict[str, Any], ack_sla_ms: int = 1500) -> dict[str, Any]:
    state = LIFECYCLE_STORE.create(payload)
    ack = LIFECYCLE_STORE.ack(state.event_id, sla_ms=ack_sla_ms)
    return {
        "ok": True,
        "event_id": state.event_id,
        "status": "queued",
        "emoji": "⏳",
        "ack": ack,
    }
