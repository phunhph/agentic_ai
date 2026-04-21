import sqlalchemy as sa

from storage.database import Base


hbl_account_industry_choice = sa.Table(
    "hbl_account_industry_choice",
    Base.metadata,
    sa.Column("hbl_accountid", sa.String(64), sa.ForeignKey("hbl_account.hbl_accountid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_account_country_choice = sa.Table(
    "hbl_account_country_choice",
    Base.metadata,
    sa.Column("hbl_accountid", sa.String(64), sa.ForeignKey("hbl_account.hbl_accountid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_account_revenue_choice = sa.Table(
    "hbl_account_revenue_choice",
    Base.metadata,
    sa.Column("hbl_accountid", sa.String(64), sa.ForeignKey("hbl_account.hbl_accountid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_contact_source_choice_map = sa.Table(
    "hbl_contact_source_choice_map",
    Base.metadata,
    sa.Column("hbl_contactid", sa.String(64), sa.ForeignKey("hbl_contact.hbl_contactid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_opportunities_status_choice_map = sa.Table(
    "hbl_opportunities_status_choice_map",
    Base.metadata,
    sa.Column("hbl_opportunitiesid", sa.String(64), sa.ForeignKey("hbl_opportunities.hbl_opportunitiesid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_contract_status_choice_map = sa.Table(
    "hbl_contract_status_choice_map",
    Base.metadata,
    sa.Column("hbl_contractid", sa.String(64), sa.ForeignKey("hbl_contract.hbl_contractid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_contract_invoiced_month_choice_map = sa.Table(
    "hbl_contract_invoiced_month_choice_map",
    Base.metadata,
    sa.Column("hbl_contractid", sa.String(64), sa.ForeignKey("hbl_contract.hbl_contractid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_contract_paid_month_choice_map = sa.Table(
    "hbl_contract_paid_month_choice_map",
    Base.metadata,
    sa.Column("hbl_contractid", sa.String(64), sa.ForeignKey("hbl_contract.hbl_contractid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)

hbl_contract_contract_month_choice_map = sa.Table(
    "hbl_contract_contract_month_choice_map",
    Base.metadata,
    sa.Column("hbl_contractid", sa.String(64), sa.ForeignKey("hbl_contract.hbl_contractid"), primary_key=True),
    sa.Column("choice_optionid", sa.String(64), sa.ForeignKey("choice_option.choice_optionid"), primary_key=True),
)
