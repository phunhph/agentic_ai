"""
DANN - Long-Term Memory System
Stores CEO/Senior sales playbooks, patterns, and neural reasoning loops.
Uses Chain-of-Thought and Tree-of-Thoughts for complex reasoning.
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LongTermMemory


class LongTermMemoryManager:
    """
    Manages persistent knowledge:
    - Sales playbooks from CEO/Senior reps
    - Detected patterns (deal stall signals, objection types)
    - Escalation history
    - CoT reasoning traces for learning
    """

    async def store_memory(
        self,
        session: AsyncSession,
        memory_type: str,
        title: str,
        content: str,
        source_role: str = "system",
        tags: Optional[list[str]] = None,
    ) -> LongTermMemory:
        mem = LongTermMemory(
            memory_type=memory_type,
            source_role=source_role,
            title=title,
            content=content,
            tags=tags or [],
        )
        session.add(mem)
        await session.flush()
        return mem

    async def retrieve_relevant(
        self,
        session: AsyncSession,
        query_tags: list[str],
        memory_type: Optional[str] = None,
        limit: int = 5,
    ) -> list[LongTermMemory]:
        """Retrieve memories by tag matching (semantic search simplified)"""
        stmt = select(LongTermMemory)
        if memory_type:
            stmt = stmt.where(LongTermMemory.memory_type == memory_type)
        stmt = stmt.order_by(LongTermMemory.usage_count.desc()).limit(limit * 3)
        result = await session.execute(stmt)
        memories = result.scalars().all()

        # Simple tag-based relevance scoring
        scored = []
        for mem in memories:
            mem_tags = set(mem.tags or [])
            query_set = set(query_tags)
            score = len(mem_tags & query_set)
            scored.append((score, mem))

        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:limit]]

    async def get_playbooks(
        self, session: AsyncSession, source_role: str = "ceo"
    ) -> list[LongTermMemory]:
        stmt = (
            select(LongTermMemory)
            .where(
                LongTermMemory.memory_type == "playbook",
                LongTermMemory.source_role == source_role,
            )
            .order_by(LongTermMemory.effectiveness_score.desc().nullslast())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def increment_usage(self, session: AsyncSession, memory_id: UUID):
        stmt = select(LongTermMemory).where(LongTermMemory.id == memory_id)
        result = await session.execute(stmt)
        mem = result.scalar_one_or_none()
        if mem:
            mem.usage_count = (mem.usage_count or 0) + 1

    async def seed_default_playbooks(self, session: AsyncSession):
        """Seed initial CEO/Senior playbooks for Lineage Copilot"""
        defaults = [
            {
                "memory_type": "playbook",
                "source_role": "ceo",
                "title": "Discount Escalation Protocol",
                "content": (
                    "Khi khách yêu cầu chiết khấu > 30%, không tự ý quyết định. "
                    "Yêu cầu: (1) Xác định Economic Buyer, (2) Đánh giá TCO 3 năm, "
                    "(3) Escalate CEO nếu lock-in > 2 năm. "
                    "Script: 'Cấu trúc này ngoài thẩm quyền của tôi, để tôi xin ý kiến sếp.'"
                ),
                "tags": ["discount", "escalation", "negotiation"],
            },
            {
                "memory_type": "tactic",
                "source_role": "senior_sales",
                "title": "Deal Stall Recovery - Economic Buyer",
                "content": (
                    "Deal chững > 5 ngày tại Evaluating: "
                    "Gửi email subject 'Cập nhật tiến độ [Tên dự án]'. "
                    "Hỏi thẳng: 'Ai là người phê duyệt ngân sách cuối cùng?' "
                    "Mục tiêu: Bypass Champion, tiếp cận Economic Buyer trực tiếp."
                ),
                "tags": ["stall", "deal_velocity", "economic_buyer", "evaluating"],
            },
            {
                "memory_type": "pattern",
                "source_role": "system",
                "title": "BANT Completeness Signal",
                "content": (
                    "Deal thiếu >= 2/4 BANT criteria có win rate < 20%. "
                    "Priority gap order: Budget > Timeline > Authority > Need. "
                    "Action: Active Probe cho missing fields trước khi tiến stage."
                ),
                "tags": ["bant", "qualification", "win_rate"],
            },
            {
                "memory_type": "playbook",
                "source_role": "ceo",
                "title": "ISO27001 Compliance Objection",
                "content": (
                    "Khách hàng có yêu cầu ISO27001/SOC2: "
                    "(1) Gửi Security Posture document ngay lập tức, "
                    "(2) Set up technical call với Solution Architect trong 48h, "
                    "(3) Không ký SLA standard - cần Security addendum. "
                    "Đây là dealbreaker nếu không handle đúng."
                ),
                "tags": ["compliance", "iso27001", "security", "sla"],
            },
        ]

        for d in defaults:
            # Check if already exists
            stmt = select(LongTermMemory).where(LongTermMemory.title == d["title"])
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                session.add(LongTermMemory(**d))


# Singleton
long_term_memory = LongTermMemoryManager()
