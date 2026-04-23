from storage.database import get_db
from storage.repositories.modules.accounts import (
    compare_account_owner_stats,
    count_accounts,
    create_account as repo_create_account,
    get_account_360_with_context,
    search_accounts_with_rollup,
)


def list_accounts(keyword: str = "", bd_owner_id: str | None = None, am_sales_id: str | None = None):
    with get_db() as db:
        return search_accounts_with_rollup(
            db,
            keyword,
            bd_owner_id=bd_owner_id,
            am_sales_id=am_sales_id,
        )


def get_account_overview():
    with get_db() as db:
        count = count_accounts(db)
        return [{"category": "account", "account_count": count, "total_records": count}]


def get_account_360(keyword: str):
    with get_db() as db:
        details = get_account_360_with_context(db, keyword)
        if not details:
            return {"error": "Không tìm thấy account"}
        return details


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


def compare_account_stats():
    with get_db() as db:
        return compare_account_owner_stats(db)


__all__ = ["list_accounts", "get_account_overview", "get_account_360", "create_account", "compare_account_stats"]

