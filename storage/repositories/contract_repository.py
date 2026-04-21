from sqlalchemy.orm import Session

from storage.models import HblAccount, HblContract, HblOpportunities, SystemUser


def list_contracts(db: Session, customer_name: str | None = None) -> list[HblContract]:
    query = db.query(HblContract)
    if customer_name:
        query = query.filter(HblContract.hbl_contract_name.ilike(f"%{customer_name}%"))
    return query.all()


def get_contract(db: Session, contract_id: str) -> HblContract | None:
    return db.query(HblContract).filter(HblContract.hbl_contractid == contract_id).first()


def get_opportunity_name(db: Session, opportunity_id: str | None) -> str | None:
    if not opportunity_id:
        return None
    row = db.query(HblOpportunities).filter(HblOpportunities.hbl_opportunitiesid == opportunity_id).first()
    return row.hbl_opportunities_name if row else None


def list_contracts_with_context(db: Session, customer_name: str | None = None) -> list[dict]:
    rows = list_contracts(db, customer_name)
    if not rows:
        return []

    opp_ids = [r.hbl_contract_opportunityid for r in rows if r.hbl_contract_opportunityid]
    owner_ids = [r.mc_contract_assigneeid for r in rows if r.mc_contract_assigneeid]

    opps = db.query(HblOpportunities).filter(HblOpportunities.hbl_opportunitiesid.in_(opp_ids)).all() if opp_ids else []
    opp_map = {o.hbl_opportunitiesid: o for o in opps}
    account_ids = [o.hbl_opportunities_accountid for o in opps if o.hbl_opportunities_accountid]
    accounts = db.query(HblAccount).filter(HblAccount.hbl_accountid.in_(account_ids)).all() if account_ids else []
    account_map = {a.hbl_accountid: a for a in accounts}
    users = db.query(SystemUser).filter(SystemUser.systemuserid.in_(owner_ids)).all() if owner_ids else []
    user_map = {u.systemuserid: u.fullname for u in users}

    result: list[dict] = []
    for c in rows:
        opp = opp_map.get(c.hbl_contract_opportunityid)
        account = account_map.get(opp.hbl_opportunities_accountid) if opp else None
        status_opts = list(c.hbl_contract_status_choice_map_options or [])
        status_label = status_opts[0].choice_label if status_opts else None
        result.append(
            {
                "order_id": c.hbl_contractid,
                "contract_name": c.hbl_contract_name,
                "customer": account.hbl_account_name if account else None,
                "opportunity": opp.hbl_opportunities_name if opp else None,
                "assignee": user_map.get(c.mc_contract_assigneeid),
                "status": status_label,
                "total": _sum_contract_value(c),
                "date": str(c.createdon) if c.createdon else None,
            }
        )
    return result


def get_contract_details_with_context(db: Session, contract_id: str) -> dict | None:
    c = get_contract(db, contract_id)
    if not c:
        return None

    opp = (
        db.query(HblOpportunities).filter(HblOpportunities.hbl_opportunitiesid == c.hbl_contract_opportunityid).first()
        if c.hbl_contract_opportunityid
        else None
    )
    account = (
        db.query(HblAccount).filter(HblAccount.hbl_accountid == opp.hbl_opportunities_accountid).first()
        if opp and opp.hbl_opportunities_accountid
        else None
    )
    assignee = (
        db.query(SystemUser).filter(SystemUser.systemuserid == c.mc_contract_assigneeid).first()
        if c.mc_contract_assigneeid
        else None
    )
    status_opts = [x.choice_label for x in (c.hbl_contract_status_choice_map_options or [])]
    invoiced_months = [x.choice_label for x in (c.hbl_contract_invoiced_month_choice_map_options or [])]
    paid_months = [x.choice_label for x in (c.hbl_contract_paid_month_choice_map_options or [])]
    contract_months = [x.choice_label for x in (c.hbl_contract_contract_month_choice_map_options or [])]

    return {
        "order_id": c.hbl_contractid,
        "customer": account.hbl_account_name if account else c.hbl_contract_name,
        "status": ", ".join(status_opts) if status_opts else None,
        "items": [
            {
                "product": opp.hbl_opportunities_name if opp else None,
                "quantity": None,
                "price": _sum_contract_value(c),
            }
        ],
        "meta": {
            "contract_name": c.hbl_contract_name,
            "assignee": assignee.fullname if assignee else None,
            "invoiced_months": invoiced_months,
            "paid_months": paid_months,
            "contract_months": contract_months,
        },
    }


def _sum_contract_value(contract: HblContract) -> float:
    months = [
        contract.hbl_contract_jan,
        contract.hbl_contract_feb,
        contract.hbl_contract_mar,
        contract.hbl_contract_apr,
        contract.hbl_contract_may,
        contract.hbl_contract_jun,
        contract.hbl_contract_jul,
        contract.hbl_contract_aug,
        contract.hbl_contract_sep,
        contract.hbl_contract_oct,
        contract.hbl_contract_nov,
        contract.hbl_contract_dec,
    ]
    return float(sum(float(v or 0) for v in months))
