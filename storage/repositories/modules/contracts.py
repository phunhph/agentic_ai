import sqlalchemy as sa
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from storage.models import HblAccount, HblContract, HblOpportunities, SystemUser


def list_contracts(db: Session, customer_name: str | None = None) -> list[HblContract]:
    query = db.query(HblContract)
    if customer_name:
        token = f"%{customer_name}%"
        query = (
            query.outerjoin(
                HblOpportunities,
                HblContract.hbl_contract_opportunityid == HblOpportunities.hbl_opportunitiesid,
            )
            .outerjoin(
                HblAccount,
                HblOpportunities.hbl_opportunities_accountid == HblAccount.hbl_accountid,
            )
            .filter(
                sa.or_(
                    HblContract.hbl_contract_name.ilike(token),
                    HblOpportunities.hbl_opportunities_name.ilike(token),
                    HblAccount.hbl_account_name.ilike(token),
                )
            )
        )
    return query.order_by(HblContract.createdon.desc()).all()


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
                "contract_name": c.hbl_contract_name,
                "contract_id": c.hbl_contractid,
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
        "contract_id": c.hbl_contractid,
        "customer": account.hbl_account_name if account else c.hbl_contract_name,
        "status": ", ".join(status_opts) if status_opts else None,
        "items": [
            {
                "name": opp.hbl_opportunities_name if opp else None,
                "quantity": None,
                "value": _sum_contract_value(c),
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


def create_contract(
    db: Session,
    *,
    contract_name: str,
    customer_name: str | None = None,
    assignee_id: str | None = None,
) -> dict:
    opportunity_id = None
    if (customer_name or "").strip():
        opp = (
            db.query(HblOpportunities)
            .outerjoin(HblAccount, HblOpportunities.hbl_opportunities_accountid == HblAccount.hbl_accountid)
            .filter(HblAccount.hbl_account_name.ilike(f"%{customer_name.strip()}%"))
            .order_by(HblOpportunities.createdon.desc())
            .first()
        )
        if opp:
            opportunity_id = opp.hbl_opportunitiesid
    row = HblContract(
        hbl_contractid=str(uuid.uuid4()),
        hbl_contract_name=(contract_name or "").strip(),
        hbl_contract_opportunityid=opportunity_id,
        mc_contract_assigneeid=(assignee_id or "").strip() or None,
        createdon=datetime.utcnow(),
        modifiedon=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "contract_id": row.hbl_contractid,
        "contract_name": row.hbl_contract_name,
        "customer_name": customer_name,
        "assignee_id": row.mc_contract_assigneeid,
        "created": True,
    }


def compare_contract_stats(db: Session) -> list[dict]:
    rows = (
        db.query(
            HblContract.mc_contract_assigneeid.label("assignee_id"),
            sa.func.count(HblContract.hbl_contractid).label("contract_count"),
            sa.func.coalesce(
                sa.func.sum(
                    sa.func.coalesce(HblContract.hbl_contract_jan, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_feb, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_mar, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_apr, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_may, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_jun, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_jul, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_aug, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_sep, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_oct, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_nov, 0.0)
                    + sa.func.coalesce(HblContract.hbl_contract_dec, 0.0)
                ),
                0.0,
            ).label("total_contract_value"),
        )
        .group_by(HblContract.mc_contract_assigneeid)
        .all()
    )
    assignee_ids = [str(r.assignee_id) for r in rows if r.assignee_id]
    users = db.query(SystemUser).filter(SystemUser.systemuserid.in_(assignee_ids)).all() if assignee_ids else []
    user_map = {u.systemuserid: u.fullname for u in users}
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "assignee_id": str(r.assignee_id) if r.assignee_id else None,
                "assignee_name": user_map.get(str(r.assignee_id), "Unassigned") if r.assignee_id else "Unassigned",
                "contract_count": int(r.contract_count or 0),
                "total_contract_value": float(r.total_contract_value or 0.0),
            }
        )
    out.sort(key=lambda x: x["contract_count"], reverse=True)
    return out


__all__ = [
    "list_contracts",
    "get_contract",
    "get_opportunity_name",
    "list_contracts_with_context",
    "get_contract_details_with_context",
    "create_contract",
    "compare_contract_stats",
]

