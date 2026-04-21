DOMAIN_MAP = {
    "INVENTORY_DOMAIN": ["hbl_account", "choice_option"],
    "SALES_DOMAIN": ["hbl_contact", "hbl_opportunities", "hbl_contract", "systemuser"],
    "ACCOUNTING_HOME": ["hbl_contract"],
}

DETAILED_SCHEMA = {
    "hbl_account": "Columns: hbl_accountid, hbl_account_name, cr987_account_am_salesid, cr987_account_bdid, createdon, modifiedon",
    "hbl_contact": "Columns: hbl_contactid, hbl_contact_name, hbl_contact_accountid, mc_contact_assigneeid, email/phone/time fields",
    "hbl_opportunities": "Columns: hbl_opportunitiesid, hbl_opportunities_name, hbl_opportunities_accountid, mc_opportunities_ownerid",
    "hbl_contract": "Columns: hbl_contractid, hbl_contract_name, hbl_contract_opportunityid, mc_contract_assigneeid, jan..dec",
    "systemuser": "Columns: systemuserid, fullname, email",
    "choice_option": "Columns: choice_optionid, choice_group, choice_code, choice_label",
}


def get_relevant_schema(intent_domain: str):
    """Máy học sẽ gọi hàm này để lấy đúng mảnh xương rồng nó cần"""
    tables = DOMAIN_MAP.get(intent_domain, [])
    return {t: DETAILED_SCHEMA[t] for t in tables if t in DETAILED_SCHEMA}
