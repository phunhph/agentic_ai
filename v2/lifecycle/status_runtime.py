from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EventState:
    event_id: str
    payload: dict[str, Any]
    received_at: str
    received_perf: float
    acked_at: str = ""
    ack_latency_ms: int = 0
    ack_sla_breached: bool = False
    first_status_at: str = ""
    processing_started_at: str = ""
    processing_finished_at: str = ""
    lifecycle: list[dict[str, Any]] = field(default_factory=list)
    status: str = "queued"
    result: dict[str, Any] | None = None
    error: str = ""


class LifecycleStore:
    def __init__(self) -> None:
        self._items: dict[str, EventState] = {}
        self._lock = Lock()

    def create(self, payload: dict[str, Any]) -> EventState:
        event_id = str(uuid4())
        state = EventState(
            event_id=event_id,
            payload=payload,
            received_at=_now_iso(),
            received_perf=perf_counter(),
        )
        self._append_lifecycle(state, "queued", {"note": "event_received"})
        with self._lock:
            self._items[event_id] = state
        return state

    def ack(self, event_id: str, sla_ms: int = 1500) -> dict[str, Any]:
        with self._lock:
            item = self._items.get(event_id)
            if not item:
                return {"ok": False, "error": "event_not_found"}
            latency = max(0, int((perf_counter() - item.received_perf) * 1000))
            item.acked_at = _now_iso()
            item.ack_latency_ms = latency
            item.ack_sla_breached = latency > int(sla_ms)
            if not item.first_status_at:
                item.first_status_at = item.acked_at
            return {
                "ok": True,
                "event_id": event_id,
                "ack_latency_ms": latency,
                "ack_sla_ms": int(sla_ms),
                "ack_sla_breached": item.ack_sla_breached,
            }

    def mark(self, event_id: str, status: str, data: dict[str, Any] | None = None) -> None:
        payload = data or {}
        with self._lock:
            item = self._items.get(event_id)
            if not item:
                return
            if status == "processing" and not item.processing_started_at:
                item.processing_started_at = _now_iso()
            if status in {"done", "clarify", "error"}:
                item.processing_finished_at = _now_iso()
            item.status = status
            if not item.first_status_at:
                item.first_status_at = _now_iso()
            self._append_lifecycle(item, status, payload)

    def set_result(self, event_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            item = self._items.get(event_id)
            if not item:
                return
            item.result = result

    def set_error(self, event_id: str, error: str) -> None:
        with self._lock:
            item = self._items.get(event_id)
            if not item:
                return
            item.error = str(error)

    def get(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(event_id)
            if not item:
                return None
            return {
                "event_id": item.event_id,
                "payload": item.payload,
                "received_at": item.received_at,
                "acked_at": item.acked_at,
                "ack_latency_ms": item.ack_latency_ms,
                "ack_sla_breached": item.ack_sla_breached,
                "first_status_at": item.first_status_at,
                "processing_started_at": item.processing_started_at,
                "processing_finished_at": item.processing_finished_at,
                "status": item.status,
                "lifecycle": list(item.lifecycle),
                "result": item.result,
                "error": item.error,
            }

    def _append_lifecycle(self, item: EventState, status: str, data: dict[str, Any]) -> None:
        item.lifecycle.append(
            {
                "ts": _now_iso(),
                "status": status,
                "emoji": self._status_emoji(status),
                "data": data,
            }
        )

    @staticmethod
    def _status_emoji(status: str) -> str:
        mapping = {
            "queued": "⏳",
            "analyzing": "📊",
            "processing": "🛠️",
            "done": "✅",
            "clarify": "❓",
            "error": "❌",
        }
        return mapping.get(status, "⏳")


LIFECYCLE_STORE = LifecycleStore()
