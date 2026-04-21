import re

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


def search_accounts(db: Session, keyword: str) -> list[HblAccount]:
    if not (keyword or "").strip():
        return db.query(HblAccount).order_by(HblAccount.createdon.desc()).limit(100).all()
    results: list[HblAccount] = []
    for candidate in _build_search_candidates(keyword):
        results = db.query(HblAccount).filter(HblAccount.hbl_account_name.ilike(f"%{candidate}%")).all()
        if results:
            break
    return results


def count_accounts(db: Session) -> int:
    return db.query(HblAccount).count()


def search_accounts_with_rollup(db: Session, keyword: str) -> list[dict]:
    accounts = search_accounts(db, keyword)
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
