import re
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from storage.models import HblAccount, HblContact, SystemUser

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


def list_contacts_with_context(db: Session, keyword: str = "", customer_name: str | None = None) -> list[dict]:
    contacts: list[HblContact] = []
    keyword_candidates = _build_search_candidates(keyword)
    customer_candidates = _build_search_candidates(customer_name or "")
    has_keyword = bool((keyword or "").strip())
    has_customer = bool((customer_name or "").strip())

    base_query = db.query(HblContact).outerjoin(HblAccount, HblContact.hbl_contact_accountid == HblAccount.hbl_accountid)

    if not has_keyword and not has_customer:
        contacts = base_query.order_by(HblContact.createdon.desc()).limit(100).all()
    else:
        for candidate in keyword_candidates:
            customer_token = customer_candidates[0] if customer_candidates else ""
            token = f"%{candidate}%"
            query = base_query
            if has_keyword:
                query = query.filter(
                    (HblContact.hbl_contact_name.ilike(token))
                    | (HblContact.hbl_contact_email.ilike(token))
                    | (HblContact.hbl_contact_phone.ilike(token))
                )
            if has_customer:
                ctoken = f"%{customer_token}%"
                query = query.filter(HblAccount.hbl_account_name.ilike(ctoken))
            contacts = query.order_by(HblContact.createdon.desc()).all()
            if contacts:
                break

    if not contacts:
        return []

    account_ids = [c.hbl_contact_accountid for c in contacts if c.hbl_contact_accountid]
    assignee_ids = [c.mc_contact_assigneeid for c in contacts if c.mc_contact_assigneeid]
    accounts = db.query(HblAccount).filter(HblAccount.hbl_accountid.in_(account_ids)).all() if account_ids else []
    assignees = db.query(SystemUser).filter(SystemUser.systemuserid.in_(assignee_ids)).all() if assignee_ids else []
    account_map = {a.hbl_accountid: a.hbl_account_name for a in accounts}
    assignee_map = {u.systemuserid: u.fullname for u in assignees}

    return [
        {
            "contact_id": c.hbl_contactid,
            "contact_name": c.hbl_contact_name,
            "title": c.hbl_contact_title,
            "email": c.hbl_contact_email,
            "phone": c.hbl_contact_phone,
            "customer": account_map.get(c.hbl_contact_accountid),
            "assignee": assignee_map.get(c.mc_contact_assigneeid),
            "next_action_date": str(c.hbl_contact_next_action_date) if c.hbl_contact_next_action_date else None,
        }
        for c in contacts
    ]


def create_contact(
    db: Session,
    *,
    contact_name: str,
    customer_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    title: str | None = None,
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
    row = HblContact(
        hbl_contactid=str(uuid.uuid4()),
        hbl_contact_name=(contact_name or "").strip(),
        hbl_contact_accountid=account_id,
        hbl_contact_email=(email or "").strip() or None,
        hbl_contact_phone=(phone or "").strip() or None,
        hbl_contact_title=(title or "").strip() or None,
        createdon=datetime.utcnow(),
        modifiedon=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "contact_id": row.hbl_contactid,
        "contact_name": row.hbl_contact_name,
        "email": row.hbl_contact_email,
        "phone": row.hbl_contact_phone,
        "title": row.hbl_contact_title,
        "customer_name": customer_name,
        "created": True,
    }


def compare_contact_stats(db: Session) -> list[dict]:
    assignees = db.query(SystemUser).all()
    out: list[dict] = []
    for user in assignees:
        count = (
            db.query(HblContact)
            .filter(HblContact.mc_contact_assigneeid == user.systemuserid)
            .count()
        )
        out.append(
            {
                "assignee_id": user.systemuserid,
                "assignee_name": user.fullname,
                "contact_count": int(count),
            }
        )
    unassigned = db.query(HblContact).filter(HblContact.mc_contact_assigneeid.is_(None)).count()
    out.append(
        {
            "assignee_id": None,
            "assignee_name": "Unassigned",
            "contact_count": int(unassigned),
        }
    )
    out.sort(key=lambda x: x["contact_count"], reverse=True)
    return out


__all__ = [
    "list_contacts_with_context",
    "create_contact",
    "compare_contact_stats",
]

