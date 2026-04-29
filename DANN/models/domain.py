from sqlalchemy import Column, String, Numeric, DateTime, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from core.database import Base
import uuid

class Opportunity(Base):
    __tablename__ = "hbl_opportunities"
    
    hbl_opportunitiesid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hbl_opportunities_name = Column(String, nullable=False)
    hbl_opportunities_account = Column(UUID(as_uuid=True), nullable=True) # lookup to hbl_account
    
    # BANT Fields (RichText map to String)
    hbl_opportunities_bant_authority = Column(String)
    hbl_opportunities_bant_need = Column(String)
    hbl_opportunities_bant_time = Column(String)
    
    # Choice Fields (Mã số từ db.json)[cite: 6]
    hbl_opportunities_request_type = Column(String) # choice[cite: 6]
    hbl_opportunities_status = Column(String) # choice: 135150000=Following...[cite: 6]
    hbl_opportunities_estimated_value = Column(Numeric)
    
    # Metadata & Flexible data[cite: 4]
    mixs = Column(JSONB, server_default=text("'{}'::jsonb"))
    createdon = Column(DateTime, server_default=text("now()"))

class Account(Base):
    __tablename__ = "hbl_account"
    hbl_accountid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hbl_account_name = Column(String, nullable=False)
    mc_account_industry = Column(String) # choice[cite: 6]
    mc_account_type = Column(String) # choice: Mega, Medium, Small[cite: 6]
    hbl_account_annual_it_budget = Column(Numeric)