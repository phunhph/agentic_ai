import re
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from storage.models import HblAccount, HblContact, HblContract, HblOpportunities, SystemUser

_TEXT_NORMALIZER_PATTERN = re.compile(
    r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]"
)


def _normalize_text(value: str) -> str:
    return " ".join(_TEXT_NORMALIZER_PATTERN.sub(" ", (value or "").lower()).split())


def _build_search_candidates(keyword: str) -> list[str]:
    raw = (keyword or "").strip()
    if not raw:
        return [""]
    normalized = _normalize_text(raw)
    return [c for c in (raw, normalized) if c]


def search_accounts(
    db: Session,
    keyword: str,
    *,
    bd_owner_id: str | None = None,
    am_sales_id: str | None = None,
) -> list[HblAccount]:
    query = db.query(HblAccount)
    if bd_owner_id:
        query = query.filter(HblAccount.cr987_account_bdid == str(bd_owner_id))
    if am_sales_id:
        query = query.filter(HblAccount.cr987_account_am_salesid == str(am_sales_id))
    if not (keyword or "").strip():
        return query.order_by(HblAccount.createdon.desc()).limit(100).all()
    results: list[HblAccount] = []
    for candidate in _build_search_candidates(keyword):
        results = query.filter(HblAccount.hbl_account_name.ilike(f"%{candidate}%")).all()
        if results:
            break
    return results


def count_accounts(db: Session) -> int:
    return db.query(HblAccount).count()


def create_account(
    db: Session,
    *,
    name: str,
    website: str | None = None,
    domain: str | None = None,
    bd_owner_id: str | None = None,
    am_sales_id: str | None = None,
) -> dict:
    account = HblAccount(
        hbl_accountid=str(uuid.uuid4()),
        hbl_account_name=(name or "").strip(),
        hbl_account_website=(website or "").strip() or None,
        hbl_account_special_domain=(domain or "").strip() or None,
        cr987_account_bdid=(bd_owner_id or "").strip() or None,
        cr987_account_am_salesid=(am_sales_id or "").strip() or None,
        createdon=datetime.utcnow(),
        modifiedon=datetime.utcnow(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {
        "id": account.hbl_accountid,
        "name": account.hbl_account_name,
        "website": account.hbl_account_website,
        "domain": account.hbl_account_special_domain,
        "bd_owner_id": account.cr987_account_bdid,
        "am_sales_id": account.cr987_account_am_salesid,
        "created": True,
    }


def compare_account_owner_stats(db: Session) -> list[dict]:
    rows = (
        db.query(
            HblAccount.cr987_account_bdid.label("owner_id"),
            sa.func.count(HblAccount.hbl_accountid).label("account_count"),
            sa.func.coalesce(sa.func.sum(HblAccount.hbl_account_annual_it_budget), 0.0).label("total_it_budget"),
        )
        .group_by(HblAccount.cr987_account_bdid)
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
                "account_count": int(r.account_count or 0),
                "total_it_budget": float(r.total_it_budget or 0.0),
            }
        )
    out.sort(key=lambda x: x["account_count"], reverse=True)
    return out


def search_accounts_with_rollup(
    db: Session,
    keyword: str,
    *,
    bd_owner_id: str | None = None,
    am_sales_id: str | None = None,
) -> list[dict]:
    accounts = search_accounts(db, keyword, bd_owner_id=bd_owner_id, am_sales_id=am_sales_id)
    if not accounts:
        return []

    account_ids = [a.hbl_accountid for a in accounts]
    owner_ids = {a.cr987_account_am_salesid for a in accounts if a.cr987_account_am_salesid} | {
        a.cr987_account_bdid for a in accounts if a.cr987_account_bdid
    }
    users = db.query(SystemUser).filter(SystemUser.systemuserid.in_(owner_ids)).all() if owner_ids else []
    user_map = {u.systemuserid: u.fullname for u in users}

    contact_counts = dict(
        db.query(HblContact.hbl_contact_accountid, sa.func.count(HblContact.hbl_contactid))
        .filter(HblContact.hbl_contact_accountid.in_(account_ids))
        .group_by(HblContact.hbl_contact_accountid)
        .all()
    )
    opp_counts = dict(
        db.query(HblOpportunities.hbl_opportunities_accountid, sa.func.count(HblOpportunities.hbl_opportunitiesid))
        .filter(HblOpportunities.hbl_opportunities_accountid.in_(account_ids))
        .group_by(HblOpportunities.hbl_opportunities_accountid)
        .all()
    )
    contract_counts = dict(
        db.query(HblOpportunities.hbl_opportunities_accountid, sa.func.count(HblContract.hbl_contractid))
        .outerjoin(HblContract, HblContract.hbl_contract_opportunityid == HblOpportunities.hbl_opportunitiesid)
        .filter(HblOpportunities.hbl_opportunities_accountid.in_(account_ids))
        .group_by(HblOpportunities.hbl_opportunities_accountid)
        .all()
    )

    return [
        {
            "id": a.hbl_accountid,
            "name": a.hbl_account_name,
            "website": a.hbl_account_website,
            "domain": a.hbl_account_special_domain,
            "am_sales": user_map.get(a.cr987_account_am_salesid),
            "bd_owner": user_map.get(a.cr987_account_bdid),
            "contact_count": int(contact_counts.get(a.hbl_accountid, 0)),
            "opportunity_count": int(opp_counts.get(a.hbl_accountid, 0)),
            "contract_count": int(contract_counts.get(a.hbl_accountid, 0)),
        }
        for a in accounts
    ]


def get_account_360_with_context(db: Session, keyword: str) -> dict | None:
    accounts = search_accounts(db, keyword)
    if not accounts:
        return None
    account = accounts[0]
    account_id = account.hbl_accountid

    contacts = (
        db.query(HblContact)
        .filter(HblContact.hbl_contact_accountid == account_id)
        .order_by(HblContact.createdon.desc())
        .limit(20)
        .all()
    )
    opportunities = (
        db.query(HblOpportunities)
        .filter(HblOpportunities.hbl_opportunities_accountid == account_id)
        .order_by(HblOpportunities.createdon.desc())
        .limit(20)
        .all()
    )
    opp_ids = [o.hbl_opportunitiesid for o in opportunities if o.hbl_opportunitiesid]
    contracts = (
        db.query(HblContract)
        .filter(HblContract.hbl_contract_opportunityid.in_(opp_ids))
        .order_by(HblContract.createdon.desc())
        .limit(20)
        .all()
        if opp_ids
        else []
    )

    owner_ids = {
        account.cr987_account_am_salesid,
        account.cr987_account_bdid,
        *[c.mc_contact_assigneeid for c in contacts if c.mc_contact_assigneeid],
        *[ct.mc_contract_assigneeid for ct in contracts if ct.mc_contract_assigneeid],
    }
    owner_ids = {x for x in owner_ids if x}
    users = db.query(SystemUser).filter(SystemUser.systemuserid.in_(owner_ids)).all() if owner_ids else []
    user_map = {u.systemuserid: u.fullname for u in users}

    opp_map = {o.hbl_opportunitiesid: o.hbl_opportunities_name for o in opportunities}

    return {
        "account": {
            "id": account.hbl_accountid,
            "name": account.hbl_account_name,
            "website": account.hbl_account_website,
            "domain": account.hbl_account_special_domain,
            "am_sales": user_map.get(account.cr987_account_am_salesid),
            "bd_owner": user_map.get(account.cr987_account_bdid),
        },
        "contacts": [
            {
                "contact_id": c.hbl_contactid,
                "contact_name": c.hbl_contact_name,
                "title": c.hbl_contact_title,
                "email": c.hbl_contact_email,
                "phone": c.hbl_contact_phone,
                "assignee": user_map.get(c.mc_contact_assigneeid),
            }
            for c in contacts
        ],
        "opportunities": [
            {
                "opportunity_id": o.hbl_opportunitiesid,
                "opportunity_name": o.hbl_opportunities_name,
                "owner_id": o.cr987_opportunities_ownerid,
                "estimated_value": float(o.cr987_opportunities_estimated_value or 0.0),
            }
            for o in opportunities
        ],
        "contracts": [
            {
                "contract_id": ct.hbl_contractid,
                "contract_name": ct.hbl_contract_name,
                "opportunity": opp_map.get(ct.hbl_contract_opportunityid),
                "assignee": user_map.get(ct.mc_contract_assigneeid),
            }
            for ct in contracts
        ],
        "summary": {
            "contact_count": len(contacts),
            "opportunity_count": len(opportunities),
            "contract_count": len(contracts),
        },
    }


__all__ = [
    "search_accounts",
    "count_accounts",
    "search_accounts_with_rollup",
    "get_account_360_with_context",
    "create_account",
    "compare_account_owner_stats",
]

