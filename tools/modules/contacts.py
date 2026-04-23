from storage.database import get_db
from storage.repositories.modules.contacts import (
    compare_contact_stats,
    create_contact as repo_create_contact,
    get_contact_details_with_context,
    list_contacts_with_context,
)


def list_contacts(keyword: str = "", customer_name: str | None = None):
    with get_db() as db:
        return list_contacts_with_context(db, keyword, customer_name=customer_name)


def get_contact_details(contact_id: str | None = None, keyword: str | None = None):
    with get_db() as db:
        details = get_contact_details_with_context(db, contact_id=contact_id, keyword=keyword)
        if not details:
            return {"error": "Không tìm thấy contact"}
        return details


def create_contact(
    contact_name: str,
    customer_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    title: str | None = None,
):
    if not str(contact_name or "").strip():
        return [{"error": "contact_name is required"}]
    with get_db() as db:
        return [
            repo_create_contact(
                db,
                contact_name=contact_name,
                customer_name=customer_name,
                email=email,
                phone=phone,
                title=title,
            )
        ]


def compare_contact_stats_tool():
    with get_db() as db:
        return compare_contact_stats(db)


__all__ = ["list_contacts", "get_contact_details", "create_contact", "compare_contact_stats_tool"]

