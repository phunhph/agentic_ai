import sqlalchemy as sa
from sqlalchemy.orm import relationship

from storage.database import Base
from storage.models.choice_links import hbl_contact_source_choice_map


class HblContact(Base):
    __tablename__ = "hbl_contact"

    hbl_contactid = sa.Column(sa.String(64), primary_key=True, nullable=False)
    hbl_contact_name = sa.Column(sa.Text, nullable=False)
    hbl_contact_title = sa.Column(sa.Text, nullable=True)
    hbl_contact_accountid = sa.Column(sa.String(64), sa.ForeignKey("hbl_account.hbl_accountid"), nullable=True)
    mc_contact_assigneeid = sa.Column(sa.String(64), sa.ForeignKey("systemuser.systemuserid"), nullable=True)
    hbl_contact_email = sa.Column(sa.Text, nullable=True)
    hbl_contact_phone = sa.Column(sa.Text, nullable=True)
    hbl_contact_linkedin = sa.Column(sa.Text, nullable=True)
    hbl_contact_birthday = sa.Column(sa.DateTime, nullable=True)
    hbl_contact_1st_mtg_time = sa.Column(sa.DateTime, nullable=True)
    hbl_contacht_last_engaged_time = sa.Column(sa.DateTime, nullable=True)
    hbl_contact_next_action_date = sa.Column(sa.DateTime, nullable=True)
    hbl_contact_social_engagement = sa.Column(sa.Float, nullable=True)
    mc_contact_interactions = sa.Column(sa.Text, nullable=True)
    hbl_contact_investigated_info = sa.Column(sa.Text, nullable=True)
    mc_contact_summary_working_history = sa.Column(sa.Text, nullable=True)
    createdon = sa.Column(sa.DateTime, nullable=True)
    modifiedon = sa.Column(sa.DateTime, nullable=True)

    account = relationship("HblAccount", back_populates="contacts")
    assignee = relationship("SystemUser", back_populates="contacts_assigned")
    hbl_contact_source_choice_map_options = relationship("ChoiceOption", secondary=hbl_contact_source_choice_map, lazy="selectin")
