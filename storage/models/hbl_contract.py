import sqlalchemy as sa
from sqlalchemy.orm import relationship

from storage.database import Base
from storage.models.choice_links import (
    hbl_contract_contract_month_choice_map,
    hbl_contract_invoiced_month_choice_map,
    hbl_contract_paid_month_choice_map,
    hbl_contract_status_choice_map,
)


class HblContract(Base):
    __tablename__ = "hbl_contract"

    hbl_contractid = sa.Column(sa.String(64), primary_key=True, nullable=False)
    hbl_contract_name = sa.Column(sa.Text, nullable=False)
    hbl_contract_opportunityid = sa.Column(sa.String(64), sa.ForeignKey("hbl_opportunities.hbl_opportunitiesid"), nullable=True)
    mc_contract_assigneeid = sa.Column(sa.String(64), sa.ForeignKey("systemuser.systemuserid"), nullable=True)
    hbl_contract_contract_drive = sa.Column(sa.Text, nullable=True)
    hbl_contract_invoices_drive = sa.Column(sa.Text, nullable=True)
    hbl_contract_start_date = sa.Column(sa.DateTime, nullable=True)
    hbl_contract_end_date = sa.Column(sa.DateTime, nullable=True)
    hbl_contract_action_date = sa.Column(sa.DateTime, nullable=True)
    hbl_contract_interactions = sa.Column(sa.Text, nullable=True)
    hbl_contract_invoice_interaction = sa.Column(sa.Text, nullable=True)
    hbl_contract_jan = sa.Column(sa.Float, nullable=True)
    hbl_contract_feb = sa.Column(sa.Float, nullable=True)
    hbl_contract_mar = sa.Column(sa.Float, nullable=True)
    hbl_contract_apr = sa.Column(sa.Float, nullable=True)
    hbl_contract_may = sa.Column(sa.Float, nullable=True)
    hbl_contract_jun = sa.Column(sa.Float, nullable=True)
    hbl_contract_jul = sa.Column(sa.Float, nullable=True)
    hbl_contract_aug = sa.Column(sa.Float, nullable=True)
    hbl_contract_sep = sa.Column(sa.Float, nullable=True)
    hbl_contract_oct = sa.Column(sa.Float, nullable=True)
    hbl_contract_nov = sa.Column(sa.Float, nullable=True)
    hbl_contract_dec = sa.Column(sa.Float, nullable=True)
    createdon = sa.Column(sa.DateTime, nullable=True)
    modifiedon = sa.Column(sa.DateTime, nullable=True)

    opportunity = relationship("HblOpportunities", back_populates="contracts")
    assignee = relationship("SystemUser", back_populates="contracts_assigned")
    hbl_contract_status_choice_map_options = relationship("ChoiceOption", secondary=hbl_contract_status_choice_map, lazy="selectin")
    hbl_contract_invoiced_month_choice_map_options = relationship("ChoiceOption", secondary=hbl_contract_invoiced_month_choice_map, lazy="selectin")
    hbl_contract_paid_month_choice_map_options = relationship("ChoiceOption", secondary=hbl_contract_paid_month_choice_map, lazy="selectin")
    hbl_contract_contract_month_choice_map_options = relationship("ChoiceOption", secondary=hbl_contract_contract_month_choice_map, lazy="selectin")
