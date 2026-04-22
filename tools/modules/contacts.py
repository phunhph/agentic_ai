from storage.database import get_db
from storage.repositories.modules.contacts import compare_contact_stats, create_contact as repo_create_contact, list_contacts_with_context


def list_contacts(keyword: str = "", customer_name: str | None = None):
    with get_db() as db:
        try:
            return list_contacts_with_context(db, keyword, customer_name=customer_name)
        except Exception:
            return []


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
        try:
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
        except Exception:
            return []


def compare_contact_stats_tool():
    with get_db() as db:
        try:
            return compare_contact_stats(db)
        except Exception:
            return []


__all__ = ["list_contacts", "create_contact", "compare_contact_stats_tool"]

