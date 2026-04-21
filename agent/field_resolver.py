from __future__ import annotations

from agent.request_contract import NormalizedRequest, RequestFilter
from storage.schema_registry import REGISTRY


INTENT_TOOL_HINT = {
    "ACCOUNT_LIST": "list_accounts",
    "CONTRACT_LIST": "list_contracts",
    "CONTRACT_DETAILS": "get_contract_details",
    "ACCOUNT_OVERVIEW": "get_account_overview",
}


def resolve_request(intent: str, entities: dict) -> NormalizedRequest:
    entities = dict(entities or {})
    filters: list[RequestFilter] = []
    unresolved: list[str] = []
    normalized_entities: dict = {}

    if intent == "ACCOUNT_LIST":
        keyword = str(entities.get("keyword", "")).strip()
        if keyword:
            normalized_entities["keyword"] = keyword
            filters.append(
                RequestFilter(
                    field="hbl_account.hbl_account_name",
                    op="contains",
                    value=keyword,
                )
            )
        # keyword có thể rỗng khi user muốn lấy toàn bộ danh sách account.

    elif intent == "CONTRACT_LIST":
        customer_name = str(entities.get("customer_name", "")).strip()
        status = str(entities.get("status", "")).strip()
        if customer_name:
            normalized_entities["customer_name"] = customer_name
            filters.append(
                RequestFilter(
                    field="hbl_contract.hbl_contract_name",
                    op="contains",
                    value=customer_name,
                )
            )
        if status:
            normalized_entities["status"] = status
            filters.append(
                RequestFilter(
                    field="choice_option.choice_label",
                    op="contains",
                    value=status,
                )
            )
        if not customer_name and not status:
            unresolved.append("customer_name|status")

    elif intent == "CONTRACT_DETAILS":
        contract_id = str(entities.get("contract_id", entities.get("order_id", ""))).strip()
        if contract_id:
            normalized_entities["contract_id"] = contract_id
            filters.append(
                RequestFilter(
                    field="hbl_contract.hbl_contractid",
                    op="eq",
                    value=contract_id,
                )
            )
        else:
            unresolved.append("contract_id")

    elif intent == "ACCOUNT_OVERVIEW":
        # Không cần filter, tool trả thống kê tổng quát
        pass
    else:
        unresolved.append("intent")

    # Validate field canonical tồn tại trong schema registry
    bad_fields = []
    for f in filters:
        if "." not in f.field:
            bad_fields.append(f.field)
            continue
        table, col = f.field.split(".", 1)
        if not REGISTRY.has_field(table, col):
            bad_fields.append(f.field)
    unresolved.extend(bad_fields)

    valid = len(unresolved) == 0
    reason = "" if valid else f"Unresolved or invalid fields: {unresolved}"
    return NormalizedRequest(
        intent=intent,
        tool_hint=INTENT_TOOL_HINT.get(intent, ""),
        entities=normalized_entities,
        filters=filters,
        unresolved_fields=unresolved,
        valid=valid,
        reason=reason,
    )
