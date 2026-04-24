from __future__ import annotations

from v2.lifecycle import LIFECYCLE_STORE
from v2.service import run_v2_pipeline


def process_event(event_id: str, goal: str, role: str = "DEFAULT", session_id: str = "", lang: str = "auto") -> None:
    try:
        LIFECYCLE_STORE.mark(event_id, "analyzing")
        LIFECYCLE_STORE.mark(event_id, "processing")
        result = run_v2_pipeline(goal, role=role, session_id=session_id, lang=lang)
        LIFECYCLE_STORE.set_result(event_id, result)
        final_state = "clarify" if str(result.get("decision_state", "")) == "ask_clarify" else "done"
        LIFECYCLE_STORE.mark(event_id, final_state)
    except Exception as e:
        LIFECYCLE_STORE.set_error(event_id, str(e))
        LIFECYCLE_STORE.mark(event_id, "error", {"detail": str(e)})
