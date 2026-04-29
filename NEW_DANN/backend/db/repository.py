"""
DANN - CRM Repository
Database CRUD operations for all entities.
Supports mixs JSON field for flexible schema.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Account, AuditLog, Contact, Opportunity, SpaceMember


class AccountRepository:
    async def find_by_name(
        self, session: AsyncSession, name: str, fuzzy: bool = True
    ) -> list[Account]:
        if fuzzy:
            stmt = select(Account).where(
                Account.hbl_account_name.ilike(f"%{name}%")
            ).limit(5)
        else:
            stmt = select(Account).where(Account.hbl_account_name == name)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, session: AsyncSession, account_id: uuid.UUID) -> Optional[Account]:
        stmt = select(Account).where(Account.hbl_accountid == account_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, name: str, **kwargs) -> Account:
        account = Account(
            hbl_accountid=uuid.uuid4(),
            hbl_account_name=name,
            **kwargs,
        )
        session.add(account)
        await session.flush()
        return account

    async def update_fields(
        self,
        session: AsyncSession,
        account: Account,
        updates: dict[str, Any],
        actor_id: str,
        chat_message_id: Optional[uuid.UUID] = None,
    ) -> list[AuditLog]:
        logs = []
        for field, new_val in updates.items():
            if not hasattr(account, field):
                # Goes to mixs
                mixs = dict(account.mixs or {})
                old_val = mixs.get(field)
                mixs[field] = new_val
                account.mixs = mixs
            else:
                old_val = getattr(account, field)
                setattr(account, field, new_val)

            log = AuditLog(
                entity_type="account",
                entity_id=account.hbl_accountid,
                action="UPDATE",
                field_name=field,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val) if new_val is not None else None,
                actor_sender_id=actor_id,
                chat_message_id=chat_message_id,
            )
            session.add(log)
            logs.append(log)
        await session.flush()
        return logs

    async def list_all(self, session: AsyncSession, limit: int = 20) -> list[Account]:
        stmt = select(Account).order_by(Account.hbl_account_name).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    def to_dict(self, account: Account) -> dict:
        return {
            "hbl_accountid": str(account.hbl_accountid),
            "hbl_account_name": account.hbl_account_name,
            "hbl_account_annual_it_budget": float(account.hbl_account_annual_it_budget or 0),
            "mc_account_industry": account.mc_account_industry,
            "mc_account_country": account.mc_account_country,
            "mc_account_market": account.mc_account_market,
            "mc_account_potential": account.mc_account_potential,
            "hbl_account_website": account.hbl_account_website,
            "hbl_account_tcv": float(account.hbl_account_tcv or 0),
            "hbl_account_total_contacts": account.hbl_account_total_contacts,
            "hbl_account_is_watching": account.hbl_account_is_watching,
            "mixs": account.mixs or {},
            "createdon": account.createdon.isoformat() if account.createdon else None,
        }


class OpportunityRepository:
    async def find_by_account(
        self, session: AsyncSession, account_id: uuid.UUID
    ) -> list[Opportunity]:
        stmt = (
            select(Opportunity)
            .where(Opportunity.hbl_account == account_id)
            .where(Opportunity.statecode == "0")
            .order_by(Opportunity.createdon.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def find_stalled(self, session: AsyncSession, days: int = 5) -> list[Opportunity]:
        """Deals with no activity > N days (Extraction Tactician trigger)"""
        from sqlalchemy import and_
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(Opportunity)
            .where(
                and_(
                    Opportunity.statecode == "0",
                    or_(
                        Opportunity.last_activity_at < cutoff,
                        Opportunity.last_activity_at.is_(None),
                    ),
                )
            )
            .limit(10)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create(
        self, session: AsyncSession, account_id: uuid.UUID, name: str, **kwargs
    ) -> Opportunity:
        opp = Opportunity(
            hbl_opportunitiesid=uuid.uuid4(),
            hbl_account=account_id,
            hbl_opportunities_name=name,
            last_activity_at=datetime.now(timezone.utc),
            **kwargs,
        )
        session.add(opp)
        await session.flush()
        return opp

    async def update_bant(
        self,
        session: AsyncSession,
        opp: Opportunity,
        budget: Optional[str] = None,
        authority: Optional[str] = None,
        need: Optional[str] = None,
        timeline: Optional[str] = None,
        stage: Optional[str] = None,
        actor_id: str = "system",
        chat_message_id: Optional[uuid.UUID] = None,
    ) -> list[AuditLog]:
        logs = []
        field_map = {
            "budget": ("hbl_opportunities_budget", budget),
            "authority": ("hbl_opportunities_authority", authority),
            "need": ("hbl_opportunities_need", need),
            "timeline": ("hbl_opportunities_timeline", timeline),
            "stage": ("hbl_opportunities_stage", stage),
        }
        for key, (db_field, new_val) in field_map.items():
            if new_val is not None:
                old_val = getattr(opp, db_field)
                setattr(opp, db_field, new_val)
                log = AuditLog(
                    entity_type="opportunity",
                    entity_id=opp.hbl_opportunitiesid,
                    action="UPDATE",
                    field_name=db_field,
                    old_value=str(old_val) if old_val else None,
                    new_value=str(new_val),
                    actor_sender_id=actor_id,
                    chat_message_id=chat_message_id,
                )
                session.add(log)
                logs.append(log)

        opp.last_activity_at = datetime.now(timezone.utc)
        await session.flush()
        return logs

    async def get_pipeline_summary(self, session: AsyncSession) -> list[dict]:
        """Pipeline overview by stage"""
        stmt = (
            select(
                Opportunity.hbl_opportunities_stage,
                func.count(Opportunity.hbl_opportunitiesid).label("count"),
                func.sum(Opportunity.hbl_opportunities_budget).label("total_budget"),
            )
            .where(Opportunity.statecode == "0")
            .group_by(Opportunity.hbl_opportunities_stage)
        )
        result = await session.execute(stmt)
        return [
            {
                "Stage": row.hbl_opportunities_stage or "Unset",
                "Deals": str(row.count),
                "Total Budget": f"${float(row.total_budget or 0):,.0f}",
            }
            for row in result.all()
        ]

    def to_dict(self, opp: Opportunity) -> dict:
        return {
            "hbl_opportunitiesid": str(opp.hbl_opportunitiesid),
            "hbl_opportunities_name": opp.hbl_opportunities_name,
            "hbl_account": str(opp.hbl_account) if opp.hbl_account else None,
            "hbl_opportunities_budget": float(opp.hbl_opportunities_budget or 0),
            "hbl_opportunities_authority": opp.hbl_opportunities_authority,
            "hbl_opportunities_need": opp.hbl_opportunities_need,
            "hbl_opportunities_timeline": opp.hbl_opportunities_timeline,
            "hbl_opportunities_stage": opp.hbl_opportunities_stage,
            "hbl_opportunities_status": opp.hbl_opportunities_status,
            "mc_opportunities_certainty": opp.mc_opportunities_certainty,
            "last_activity_at": opp.last_activity_at.isoformat() if opp.last_activity_at else None,
            "mixs": opp.mixs or {},
        }


class SpaceMemberRepository:
    async def get_by_sender_id(
        self, session: AsyncSession, sender_id: str
    ) -> Optional[SpaceMember]:
        stmt = select(SpaceMember).where(SpaceMember.sender_id == sender_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        session: AsyncSession,
        sender_id: str,
        display_name: str,
        **kwargs,
    ) -> SpaceMember:
        member = await self.get_by_sender_id(session, sender_id)
        if not member:
            member = SpaceMember(
                sender_id=sender_id,
                display_name=display_name,
                **kwargs,
            )
            session.add(member)
        else:
            member.display_name = display_name
            for k, v in kwargs.items():
                if hasattr(member, k):
                    setattr(member, k, v)
        await session.flush()
        return member

    def to_dict(self, member: SpaceMember) -> dict:
        return {
            "id": str(member.id),
            "sender_id": member.sender_id,
            "display_name": member.display_name,
            "email": member.email,
            "role": member.role,
            "experience_level": member.experience_level,
            "tone_preference": member.tone_preference,
        }


class AuditRepository:
    async def get_by_message(
        self, session: AsyncSession, chat_message_id: uuid.UUID
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.chat_message_id == chat_message_id)
            .order_by(AuditLog.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def undo_last(
        self, session: AsyncSession, chat_message_id: uuid.UUID
    ) -> bool:
        """Undo CRM changes from a specific message (best-effort)"""
        logs = await self.get_by_message(session, chat_message_id)
        if not logs:
            return False
        # Group by entity
        for log in logs:
            if log.entity_type == "opportunity":
                stmt = select(Opportunity).where(
                    Opportunity.hbl_opportunitiesid == log.entity_id
                )
                result = await session.execute(stmt)
                opp = result.scalar_one_or_none()
                if opp and log.field_name:
                    setattr(opp, log.field_name, log.old_value)
            elif log.entity_type == "account":
                stmt = select(Account).where(Account.hbl_accountid == log.entity_id)
                result = await session.execute(stmt)
                acc = result.scalar_one_or_none()
                if acc and log.field_name:
                    setattr(acc, log.field_name, log.old_value)
        await session.flush()
        return True


# Singletons
account_repo = AccountRepository()
opportunity_repo = OpportunityRepository()
space_member_repo = SpaceMemberRepository()
audit_repo = AuditRepository()
