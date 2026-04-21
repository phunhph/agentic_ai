from storage.database import get_db
from storage.repositories.contract_repository import (
    get_contract_details_with_context,
    list_contracts_with_context,
)


def get_orders(customer_name: str = None, status: str = None):
    """Lấy danh sách hợp đồng theo schema CRM mới."""
    with get_db() as db:
        results = list_contracts_with_context(db, customer_name)
        if status:
            status_upper = status.strip().upper()
            results = [row for row in results if (row.get("status") or "").upper() == status_upper]
        return results


def get_order_details(order_id: int):
    """Lấy chi tiết hợp đồng theo schema CRM mới."""
    with get_db() as db:
        details = get_contract_details_with_context(db, str(order_id))
        if not details:
            return {"error": "Không tìm thấy hợp đồng"}
        return details
