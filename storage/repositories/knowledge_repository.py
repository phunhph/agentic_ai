from __future__ import annotations

import json
import uuid
import re
from datetime import UTC, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from infra.settings import LEARNING_SCORE_WEIGHT, LEARNING_TEXT_MATCH_MIN, LEARNING_TEXT_WEIGHT
from storage.models.agent_knowledge_base import AgentKnowledgeBase

_NON_WORD = re.compile(
    r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]"
)


def _normalize_text(text: str) -> str:
    return " ".join(_NON_WORD.sub(" ", (text or "").lower()).split())


def _token_set(text: str) -> set[str]:
    return set(_normalize_text(text).split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return inter / union if union else 0.0


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
    q = _normalize_text(query)
    q_tokens = _token_set(q)
    rows = (
        db.query(AgentKnowledgeBase)
        .filter(AgentKnowledgeBase.user_role == (role or "BUYER").upper())
        .filter(AgentKnowledgeBase.domain == (domain or "general").lower())
        .filter(AgentKnowledgeBase.is_active == True)  # noqa: E712
        .order_by(desc(AgentKnowledgeBase.score), desc(AgentKnowledgeBase.updated_at))
        .limit(max(1, limit * 4))
        .all()
    )
    scored: list[tuple[float, AgentKnowledgeBase, float]] = []
    for row in rows:
        text_ref = f"{row.original_query or ''} {row.correction_text or ''}".strip()
        text_score = _jaccard(q_tokens, _token_set(text_ref))
        if q and text_score < LEARNING_TEXT_MATCH_MIN:
            continue
        db_score = float(row.score or 0.0)
        final_score = (LEARNING_SCORE_WEIGHT * db_score) + (LEARNING_TEXT_WEIGHT * text_score)
        scored.append((final_score, row, text_score))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict] = []
    for final_score, row, text_score in scored[: max(1, limit)]:
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
                "text_match_score": round(text_score, 4),
                "final_match_score": round(final_score, 4),
            }
        )
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


def penalize_lessons(
    db: Session,
    lesson_ids: list[str],
    *,
    penalty: float = 0.2,
) -> None:
    if not lesson_ids:
        return
    now = datetime.now(UTC)
    rows = db.query(AgentKnowledgeBase).filter(AgentKnowledgeBase.id.in_(lesson_ids)).all()
    for row in rows:
        row.usage_count = int(row.usage_count or 0) + 1
        row.score = max(0.0, float(row.score or 0.0) - float(max(0.0, penalty)))
        row.is_active = row.score >= 0.15
        row.last_used_at = now
        row.updated_at = now
    db.commit()


def prune_low_confidence_lessons(
    db: Session,
    *,
    role: str,
    domain: str,
    keep_top: int = 30,
) -> int:
    rows = (
        db.query(AgentKnowledgeBase)
        .filter(AgentKnowledgeBase.user_role == (role or "BUYER").upper())
        .filter(AgentKnowledgeBase.domain == (domain or "general").lower())
        .order_by(desc(AgentKnowledgeBase.score), desc(AgentKnowledgeBase.updated_at))
        .all()
    )
    if len(rows) <= keep_top:
        return 0
    removed = 0
    cutoff_score = float(rows[keep_top - 1].score or 0.0) if keep_top > 0 else 0.0
    for row in rows[keep_top:]:
        row_score = float(row.score or 0.0)
        if row_score <= cutoff_score:
            db.delete(row)
            removed += 1
        else:
            row.is_active = False
            removed += 1
    db.commit()
    return removed

