import sqlalchemy as sa
from sqlalchemy.orm import relationship

from storage.database import Base


class SystemUser(Base):
    __tablename__ = "systemuser"

    systemuserid = sa.Column(sa.String(64), primary_key=True, nullable=False)
    fullname = sa.Column(sa.Text, nullable=False)
    email = sa.Column(sa.Text, nullable=True)
    createdon = sa.Column(sa.DateTime, nullable=True)
    modifiedon = sa.Column(sa.DateTime, nullable=True)

    accounts_am_sales = relationship("HblAccount", foreign_keys="HblAccount.cr987_account_am_salesid", back_populates="am_sales")
    accounts_bd = relationship("HblAccount", foreign_keys="HblAccount.cr987_account_bdid", back_populates="bd_owner")
    contacts_assigned = relationship("HblContact", foreign_keys="HblContact.mc_contact_assigneeid", back_populates="assignee")
    opportunities_owned = relationship("HblOpportunities", foreign_keys="HblOpportunities.mc_opportunities_ownerid", back_populates="owner")
    contracts_assigned = relationship("HblContract", foreign_keys="HblContract.mc_contract_assigneeid", back_populates="assignee")
