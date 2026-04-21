import sqlalchemy as sa
from sqlalchemy.orm import relationship

from storage.database import Base
from storage.models.choice_links import (
    hbl_account_country_choice,
    hbl_account_industry_choice,
    hbl_account_revenue_choice,
)


class HblAccount(Base):
    __tablename__ = "hbl_account"

    hbl_accountid = sa.Column(sa.String(64), primary_key=True, nullable=False)
    hbl_account_name = sa.Column(sa.Text, nullable=False)
    hbl_account_physical_address = sa.Column(sa.Text, nullable=True)
    hbl_account_website = sa.Column(sa.Text, nullable=True)
    hbl_account_special_domain = sa.Column(sa.Text, nullable=True)
    hbl_account_development_ratio = sa.Column(sa.Float, nullable=True)
    hbl_account_annual_it_budget = sa.Column(sa.Float, nullable=True)
    hbl_account_year_found = sa.Column(sa.Integer, nullable=True)
    cr987_account_am_salesid = sa.Column(sa.String(64), sa.ForeignKey("systemuser.systemuserid"), nullable=True)
    cr987_account_bdid = sa.Column(sa.String(64), sa.ForeignKey("systemuser.systemuserid"), nullable=True)
    createdon = sa.Column(sa.DateTime, nullable=True)
    modifiedon = sa.Column(sa.DateTime, nullable=True)

    am_sales = relationship("SystemUser", foreign_keys=[cr987_account_am_salesid], back_populates="accounts_am_sales")
    bd_owner = relationship("SystemUser", foreign_keys=[cr987_account_bdid], back_populates="accounts_bd")
    contacts = relationship("HblContact", back_populates="account")
    opportunities = relationship("HblOpportunities", back_populates="account")

    hbl_account_industry_choice_options = relationship("ChoiceOption", secondary=hbl_account_industry_choice, lazy="selectin")
    hbl_account_country_choice_options = relationship("ChoiceOption", secondary=hbl_account_country_choice, lazy="selectin")
    hbl_account_revenue_choice_options = relationship("ChoiceOption", secondary=hbl_account_revenue_choice, lazy="selectin")
