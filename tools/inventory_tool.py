from storage.database import get_db
from storage.repositories.account_repository import count_accounts, search_accounts_with_rollup


def search_products(keyword: str):
    with get_db() as db:
        try:
            return search_accounts_with_rollup(db, keyword)
        except Exception:
            return []


def get_inventory_stats():
    with get_db() as db:
        try:
            count = count_accounts(db)
            return [{"category": "account", "product_count": count, "total_quantity": count}]
        except Exception:
            return []
