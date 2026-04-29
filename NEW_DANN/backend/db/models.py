"""
DANN - Database Models
Mapped from db.json schema (hbl_account, hbl_opportunities, hbl_contract, space_member)
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, String, Text, JSON, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class SpaceMember(Base):
    """Maps Google Chat sender IDs to CRM user profiles (Phase 1 Foundation)"""
    __tablename__ = "space_member"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sender_id = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="sales_rep")  # sales_rep | sales_manager | ceo
    experience_level = Column(String(20), nullable=False, default="junior")  # junior | senior
    tone_preference = Column(String(20), nullable=False, default="formal")  # formal | casual
    # Dynamic Profiler metrics (Phase 3)
    deal_velocity_score = Column(Numeric(5, 2), nullable=True)
    follow_up_frequency = Column(Numeric(5, 2), nullable=True)
    communication_depth = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    chat_messages = relationship("ChatMessage", back_populates="sender")


class Account(Base):
    """hbl_account - Core account/company entity"""
    __tablename__ = "hbl_account"

    hbl_accountid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    hbl_account_name = Column(String(500), nullable=False, index=True)
    # BANT fields
    hbl_account_annual_it_budget = Column(Numeric(18, 2), nullable=True)  # Budget (B)
    # Authority stored in contacts relationship
    # Need/Timeline stored in opportunities
    # Extended fields
    mc_account_industry = Column(String(100), nullable=True)
    mc_account_country = Column(String(100), nullable=True)
    mc_account_market = Column(String(100), nullable=True)
    mc_account_potential = Column(String(50), nullable=True)
    hbl_account_website = Column(String(500), nullable=True)
    hbl_account_linkedin = Column(String(500), nullable=True)
    hbl_account_physical_address = Column(Text, nullable=True)
    hbl_account_is_watching = Column(Boolean, nullable=True, default=False)
    hbl_account_tcv = Column(Numeric(18, 2), nullable=True)
    hbl_account_total_contacts = Column(Integer, nullable=True)
    hbl_account_basic_info_quality = Column(Numeric(5, 2), nullable=True)
    mc_account_investigated_info = Column(Text, nullable=True)
    # Flexible schema - captures unstructured context
    mixs = Column(JSON, nullable=True, default=dict)
    createdon = Column(DateTime(timezone=True), server_default=func.now())
    createdbyname = Column(String(255), nullable=True)

    opportunities = relationship("Opportunity", back_populates="account")
    contacts = relationship("Contact", back_populates="account")


class Opportunity(Base):
    """hbl_opportunities - Deal/Opportunity entity"""
    __tablename__ = "hbl_opportunities"

    hbl_opportunitiesid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    hbl_account = Column(UUID(as_uuid=True), ForeignKey("hbl_account.hbl_accountid"), nullable=True, index=True)
    hbl_opportunities_name = Column(String(500), nullable=False)
    # BANT
    hbl_opportunities_budget = Column(Numeric(18, 2), nullable=True)       # B - Budget
    hbl_opportunities_authority = Column(String(255), nullable=True)        # A - Authority (who decides)
    hbl_opportunities_need = Column(Text, nullable=True)                    # N - Need/Problem
    hbl_opportunities_timeline = Column(String(100), nullable=True)         # T - Timeline
    # Pipeline
    hbl_opportunities_status = Column(String(50), nullable=True)
    hbl_opportunities_stage = Column(String(100), nullable=True)
    hbl_opportunities_action_class = Column(String(50), nullable=True)
    hbl_opportunities_request_type = Column(String(50), nullable=True)
    mc_opp_market = Column(String(50), nullable=True)
    mc_opportunities_certainty = Column(String(50), nullable=True)
    hbl_opportunities_amount = Column(Numeric(18, 2), nullable=True)
    hbl_opportunities_close_date = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    # Flexible schema
    mixs = Column(JSON, nullable=True, default=dict)
    createdon = Column(DateTime(timezone=True), server_default=func.now())
    statecode = Column(String(10), nullable=True, default="0")

    account = relationship("Account", back_populates="opportunities")


class Contact(Base):
    """hbl_contact - People/Stakeholders at accounts"""
    __tablename__ = "hbl_contact"

    hbl_contactid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    hbl_account = Column(UUID(as_uuid=True), ForeignKey("hbl_account.hbl_accountid"), nullable=True, index=True)
    hbl_contact_name = Column(String(255), nullable=False)
    hbl_contact_title = Column(String(255), nullable=True)
    hbl_contact_email = Column(String(255), nullable=True)
    hbl_contact_phone = Column(String(50), nullable=True)
    hbl_contact_is_decision_maker = Column(Boolean, nullable=True, default=False)
    hbl_contact_influence_level = Column(String(20), nullable=True)  # high | medium | low
    # DISC profile (B2B intelligence)
    disc_profile = Column(String(1), nullable=True)  # D | I | S | C
    mixs = Column(JSON, nullable=True, default=dict)
    createdon = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="contacts")


class ChatMessage(Base):
    """Stores processed chat messages (ephemeral after processing per NFR4)"""
    __tablename__ = "chat_message"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sender_id = Column(String(255), ForeignKey("space_member.sender_id"), nullable=True)
    space_id = Column(String(255), nullable=True, index=True)
    message_text = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)  # QUERY | UPDATE | CREATE | HELP | COMPASS
    confidence = Column(Numeric(4, 2), nullable=True)
    processing_state = Column(String(20), nullable=True)  # queued | analyzing | processing | done | error
    agent_response = Column(JSON, nullable=True)  # Card V2 JSON
    related_account_id = Column(UUID(as_uuid=True), nullable=True)
    related_opportunity_id = Column(UUID(as_uuid=True), nullable=True)
    # Ephemeral: raw_payload is cleared after processing (NFR4)
    raw_payload_cleared = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    sender = relationship("SpaceMember", back_populates="chat_messages")


class AuditLog(Base):
    """Tracks all CRM mutations for undo functionality"""
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type = Column(String(50), nullable=False)  # account | opportunity | contact
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(20), nullable=False)  # CREATE | UPDATE | DELETE
    field_name = Column(String(255), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    actor_sender_id = Column(String(255), nullable=True)
    chat_message_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LongTermMemory(Base):
    """Long-term memory store for neural reasoning patterns (Lineage Copilot)"""
    __tablename__ = "long_term_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    memory_type = Column(String(50), nullable=False)  # tactic | playbook | pattern | escalation
    source_role = Column(String(50), nullable=True)   # ceo | senior_sales | system
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    embedding_vector = Column(JSON, nullable=True)    # Stored as JSON array for simplicity
    usage_count = Column(Integer, default=0)
    effectiveness_score = Column(Numeric(4, 2), nullable=True)
    tags = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
