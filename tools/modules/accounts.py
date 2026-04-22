from storage.database import get_db
from storage.repositories.modules.accounts import (
    compare_account_owner_stats,
    count_accounts,
    create_account as repo_create_account,
    search_accounts_with_rollup,
)


def list_accounts(keyword: str = "", bd_owner_id: str | None = None, am_sales_id: str | None = None):
    with get_db() as db:
        try:
            return search_accounts_with_rollup(
                db,
                keyword,
                bd_owner_id=bd_owner_id,
                am_sales_id=am_sales_id,
            )
        except Exception:
            return []


def get_account_overview():
    with get_db() as db:
        try:
            count = count_accounts(db)
            return [{"category": "account", "account_count": count, "total_records": count}]
        except Exception:
            return []


def create_account(
    name: str,
    website: str | None = None,
    domain: str | None = None,
    bd_owner_id: str | None = None,
    am_sales_id: str | None = None,
):
    if not str(name or "").strip():
        return [{"error": "name is required"}]
    with get_db() as db:
        try:
            return [
                repo_create_account(
                    db,
                    name=name,
                    website=website,
                    domain=domain,
                    bd_owner_id=bd_owner_id,
                    am_sales_id=am_sales_id,
                )
            ]
        except Exception:
            return []


def compare_account_stats():
    with get_db() as db:
        try:
            return compare_account_owner_stats(db)
        except Exception:
            return []


__all__ = ["list_accounts", "get_account_overview", "create_account", "compare_account_stats"]

