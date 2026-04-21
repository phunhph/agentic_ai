from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from storage.models.agent_knowledge_base import AgentKnowledgeBase


def record_correction(
    db: Session,
    *,
    context_key: str | None,
    user_role: str,
    domain: str,
    original_query: str,
    wrong_answer_excerpt: str | None,
    correction_text: str,
    error_type: str | None,
    resolved_intent: str | None,
    resolved_entities: dict | None,
) -> AgentKnowledgeBase:
    now = datetime.now(UTC)
    row = AgentKnowledgeBase(
        id=str(uuid.uuid4()),
        context_key=context_key,
        user_role=(user_role or "BUYER").upper(),
        domain=(domain or "general").lower(),
        original_query=original_query,
        wrong_answer_excerpt=wrong_answer_excerpt,
        correction_text=correction_text,
        error_type=error_type,
        resolved_intent=resolved_intent,
        resolved_entities_json=json.dumps(resolved_entities or {}, ensure_ascii=False),
        usage_count=0,
        success_count=0,
        score=0.0,
        is_active=True,
        last_used_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def find_similar_lessons(
    db: Session,
    *,
    query: str,
    role: str,
    domain: str,
    limit: int = 5,
) -> list[dict]:
    q = (query or "").strip().lower()
    rows = (
        db.query(AgentKnowledgeBase)
        .filter(AgentKnowledgeBase.user_role == (role or "BUYER").upper())
        .filter(AgentKnowledgeBase.domain == (domain or "general").lower())
        .filter(AgentKnowledgeBase.is_active == True)  # noqa: E712
        .order_by(desc(AgentKnowledgeBase.score), desc(AgentKnowledgeBase.updated_at))
        .limit(max(1, limit * 4))
        .all()
    )
    out: list[dict] = []
    for row in rows:
        if q and q not in (row.original_query or "").lower() and q not in (row.correction_text or "").lower():
            continue
        out.append(
            {
                "id": row.id,
                "original_query": row.original_query,
                "correction_text": row.correction_text,
                "resolved_intent": row.resolved_intent,
                "resolved_entities": json.loads(row.resolved_entities_json or "{}"),
                "error_type": row.error_type,
                "score": float(row.score or 0.0),
                "usage_count": int(row.usage_count or 0),
                "success_count": int(row.success_count or 0),
            }
        )
        if len(out) >= limit:
            break
    return out


def mark_lessons_outcome(db: Session, lesson_ids: list[str], *, success: bool) -> None:
    if not lesson_ids:
        return
    now = datetime.now(UTC)
    rows = db.query(AgentKnowledgeBase).filter(AgentKnowledgeBase.id.in_(lesson_ids)).all()
    for row in rows:
        row.usage_count = int(row.usage_count or 0) + 1
        if success:
            row.success_count = int(row.success_count or 0) + 1
        # score = success_ratio + confidence bonus from usage volume
        usage = max(1, int(row.usage_count or 0))
        succ = int(row.success_count or 0)
        success_ratio = succ / usage
        volume_bonus = min(0.3, usage / 100.0)
        row.score = round(success_ratio + volume_bonus, 4)
        row.is_active = row.score >= 0.15 or usage < 5
        row.last_used_at = now
        row.updated_at = now
    db.commit()

