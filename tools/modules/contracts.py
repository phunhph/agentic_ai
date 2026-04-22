from storage.database import get_db
from storage.repositories.modules.contracts import (
    compare_contract_stats,
    create_contract,
    get_contract_details_with_context,
    list_contracts_with_context,
)


def list_contracts(customer_name: str = None, status: str = None):
    with get_db() as db:
        results = list_contracts_with_context(db, customer_name)
        if status:
            status_upper = status.strip().upper()
            results = [row for row in results if (row.get("status") or "").upper() == status_upper]
        return results


def get_contract_details(contract_id: str):
    with get_db() as db:
        details = get_contract_details_with_context(db, str(contract_id))
        if not details:
            return {"error": "Không tìm thấy hợp đồng"}
        return details


def create_contract_tool(contract_name: str, customer_name: str = None, assignee_id: str = None):
    if not str(contract_name or "").strip():
        return [{"error": "contract_name is required"}]
    with get_db() as db:
        return [
            create_contract(
                db,
                contract_name=contract_name,
                customer_name=customer_name,
                assignee_id=assignee_id,
            )
        ]


def compare_contract_stats_tool():
    with get_db() as db:
        return compare_contract_stats(db)


__all__ = ["list_contracts", "get_contract_details", "create_contract_tool", "compare_contract_stats_tool"]

