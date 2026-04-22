import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from storage.models import HblAccount, HblContract, HblOpportunities, SystemUser


def list_opportunities_with_context(db: Session, keyword: str = "", customer_name: str | None = None) -> list[dict]:
    query = db.query(HblOpportunities).outerjoin(
        HblAccount,
        HblOpportunities.hbl_opportunities_accountid == HblAccount.hbl_accountid,
    )
    if (keyword or "").strip():
        token = f"%{keyword.strip()}%"
        query = query.filter(
            sa.or_(
                HblOpportunities.hbl_opportunities_name.ilike(token),
                HblAccount.hbl_account_name.ilike(token),
            )
        )
    if (customer_name or "").strip():
        ctoken = f"%{customer_name.strip()}%"
        query = query.filter(HblAccount.hbl_account_name.ilike(ctoken))

    rows = query.order_by(HblOpportunities.createdon.desc()).limit(200).all()
    if not rows:
        return []

    account_ids = [r.hbl_opportunities_accountid for r in rows if r.hbl_opportunities_accountid]
    owner_ids = [r.mc_opportunities_ownerid for r in rows if r.mc_opportunities_ownerid]
    opp_ids = [r.hbl_opportunitiesid for r in rows]

    accounts = db.query(HblAccount).filter(HblAccount.hbl_accountid.in_(account_ids)).all() if account_ids else []
    users = db.query(SystemUser).filter(SystemUser.systemuserid.in_(owner_ids)).all() if owner_ids else []
    contract_counts = dict(
        db.query(HblContract.hbl_contract_opportunityid, sa.func.count(HblContract.hbl_contractid))
        .filter(HblContract.hbl_contract_opportunityid.in_(opp_ids))
        .group_by(HblContract.hbl_contract_opportunityid)
        .all()
    )
    account_map = {a.hbl_accountid: a.hbl_account_name for a in accounts}
    user_map = {u.systemuserid: u.fullname for u in users}

    return [
        {
            "opportunity_id": r.hbl_opportunitiesid,
            "opportunity_name": r.hbl_opportunities_name,
            "customer": account_map.get(r.hbl_opportunities_accountid),
            "owner": user_map.get(r.mc_opportunities_ownerid),
            "estimated_value": float(r.hbl_opportunities_estimated_value or 0.0),
            "contract_count": int(contract_counts.get(r.hbl_opportunitiesid, 0)),
            "deadline": str(r.hbl_opportunities_deadline) if r.hbl_opportunities_deadline else None,
        }
        for r in rows
    ]


def create_opportunity(
    db: Session,
    *,
    opportunity_name: str,
    customer_name: str | None = None,
    owner_id: str | None = None,
    estimated_value: float | None = None,
) -> dict:
    account_id = None
    if (customer_name or "").strip():
        account = (
            db.query(HblAccount)
            .filter(HblAccount.hbl_account_name.ilike(f"%{customer_name.strip()}%"))
            .order_by(HblAccount.createdon.desc())
            .first()
        )
        if account:
            account_id = account.hbl_accountid

    row = HblOpportunities(
        hbl_opportunitiesid=str(uuid.uuid4()),
        hbl_opportunities_name=(opportunity_name or "").strip(),
        hbl_opportunities_accountid=account_id,
        mc_opportunities_ownerid=(owner_id or "").strip() or None,
        hbl_opportunities_estimated_value=float(estimated_value or 0.0),
        createdon=datetime.utcnow(),
        modifiedon=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "opportunity_id": row.hbl_opportunitiesid,
        "opportunity_name": row.hbl_opportunities_name,
        "customer_name": customer_name,
        "owner_id": row.mc_opportunities_ownerid,
        "estimated_value": float(row.hbl_opportunities_estimated_value or 0.0),
        "created": True,
    }


def compare_opportunity_stats(db: Session) -> list[dict]:
    rows = (
        db.query(
            HblOpportunities.mc_opportunities_ownerid.label("owner_id"),
            sa.func.count(HblOpportunities.hbl_opportunitiesid).label("opportunity_count"),
            sa.func.coalesce(sa.func.sum(HblOpportunities.hbl_opportunities_estimated_value), 0.0).label("total_estimated_value"),
        )
        .group_by(HblOpportunities.mc_opportunities_ownerid)
        .all()
    )
    owner_ids = [str(r.owner_id) for r in rows if r.owner_id]
    users = db.query(SystemUser).filter(SystemUser.systemuserid.in_(owner_ids)).all() if owner_ids else []
    user_map = {u.systemuserid: u.fullname for u in users}
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "owner_id": str(r.owner_id) if r.owner_id else None,
                "owner_name": user_map.get(str(r.owner_id), "Unassigned") if r.owner_id else "Unassigned",
                "opportunity_count": int(r.opportunity_count or 0),
                "total_estimated_value": float(r.total_estimated_value or 0.0),
            }
        )
    out.sort(key=lambda x: x["opportunity_count"], reverse=True)
    return out


__all__ = ["list_opportunities_with_context", "create_opportunity", "compare_opportunity_stats"]
