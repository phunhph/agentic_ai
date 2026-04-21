from storage.database import get_db
from storage.repositories.account_repository import count_accounts, search_accounts_with_rollup


def list_accounts(keyword: str = ""):
    with get_db() as db:
        try:
            return search_accounts_with_rollup(db, keyword)
        except Exception:
            return []


def get_account_overview():
    with get_db() as db:
        try:
            count = count_accounts(db)
            return [{"category": "account", "account_count": count, "total_records": count}]
        except Exception:
            return []
