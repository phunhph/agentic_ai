import sqlalchemy as sa
from sqlalchemy.orm import relationship

from storage.database import Base
from storage.models.choice_links import hbl_opportunities_status_choice_map


class HblOpportunities(Base):
    __tablename__ = "hbl_opportunities"

    hbl_opportunitiesid = sa.Column(sa.String(64), primary_key=True, nullable=False)
    hbl_opportunities_name = sa.Column(sa.Text, nullable=False)
    hbl_opportunities_accountid = sa.Column(sa.String(64), sa.ForeignKey("hbl_account.hbl_accountid"), nullable=True)
    mc_opportunities_ownerid = sa.Column(sa.String(64), sa.ForeignKey("systemuser.systemuserid"), nullable=True)
    hbl_opportunities_bant_authority = sa.Column(sa.Text, nullable=True)
    hbl_opportunities_bant_need = sa.Column(sa.Text, nullable=True)
    hbl_opportunities_bant_time = sa.Column(sa.Text, nullable=True)
    hbl_opportunities_estimated_value = sa.Column(sa.Float, nullable=True)
    hbl_opportunities_start_time_est = sa.Column(sa.DateTime, nullable=True)
    hbl_opportunities_end_time_est = sa.Column(sa.DateTime, nullable=True)
    hbl_opportunities_deadline = sa.Column(sa.DateTime, nullable=True)
    mc_opportunities_presales = sa.Column(sa.Text, nullable=True)
    hbl_opportunitiest_next_time_action = sa.Column(sa.Text, nullable=True)
    hbl_opportunities_interactions = sa.Column(sa.Text, nullable=True)
    createdon = sa.Column(sa.DateTime, nullable=True)
    modifiedon = sa.Column(sa.DateTime, nullable=True)

    account = relationship("HblAccount", back_populates="opportunities")
    owner = relationship("SystemUser", back_populates="opportunities_owned")
    contracts = relationship("HblContract", back_populates="opportunity")
    hbl_opportunities_status_choice_map_options = relationship("ChoiceOption", secondary=hbl_opportunities_status_choice_map, lazy="selectin")
