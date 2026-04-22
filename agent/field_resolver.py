from __future__ import annotations

from agent.request_contract import NormalizedRequest, RequestFilter
from storage.schema_registry import REGISTRY


INTENT_TOOL_HINT = {
    "ACCOUNT_LIST": "list_accounts",
    "ACCOUNT_CREATE": "create_account",
    "ACCOUNT_COMPARE": "compare_account_stats",
    "CONTACT_LIST": "list_contacts",
    "CONTACT_CREATE": "create_contact",
    "CONTACT_COMPARE": "compare_contact_stats",
    "CONTRACT_LIST": "list_contracts",
    "CONTRACT_CREATE": "create_contract",
    "CONTRACT_COMPARE": "compare_contract_stats",
    "OPPORTUNITY_LIST": "list_opportunities",
    "OPPORTUNITY_CREATE": "create_opportunity",
    "OPPORTUNITY_COMPARE": "compare_opportunity_stats",
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
        bd_owner_id = str(entities.get("bd_owner_id", "")).strip()
        am_sales_id = str(entities.get("am_sales_id", "")).strip()
        if keyword:
            normalized_entities["keyword"] = keyword
            filters.append(
                RequestFilter(
                    field="hbl_account.hbl_account_name",
                    op="contains",
                    value=keyword,
                )
            )
        if bd_owner_id:
            normalized_entities["bd_owner_id"] = bd_owner_id
            normalized_entities["bd_owner_name"] = str(entities.get("bd_owner_name", "")).strip()
            filters.append(
                RequestFilter(
                    field="hbl_account.cr987_account_bdid",
                    op="eq",
                    value=bd_owner_id,
                )
            )
        if am_sales_id:
            normalized_entities["am_sales_id"] = am_sales_id
            normalized_entities["am_sales_name"] = str(entities.get("am_sales_name", "")).strip()
            filters.append(
                RequestFilter(
                    field="hbl_account.cr987_account_am_salesid",
                    op="eq",
                    value=am_sales_id,
                )
            )
        # keyword có thể rỗng khi user muốn lấy toàn bộ danh sách account.

    elif intent == "ACCOUNT_CREATE":
        name = str(entities.get("name", entities.get("account_name", entities.get("keyword", "")))).strip()
        if name:
            normalized_entities["name"] = name
            normalized_entities["website"] = str(entities.get("website", "")).strip() or None
            normalized_entities["domain"] = str(entities.get("domain", "")).strip() or None
            normalized_entities["bd_owner_id"] = str(entities.get("bd_owner_id", "")).strip() or None
            normalized_entities["am_sales_id"] = str(entities.get("am_sales_id", "")).strip() or None
        else:
            unresolved.append("name")

    elif intent == "ACCOUNT_COMPARE":
        # Tool thống kê so sánh không bắt buộc filter đầu vào.
        pass

    elif intent == "CONTACT_LIST":
        keyword = str(entities.get("keyword", "")).strip()
        customer_name = str(entities.get("customer_name", "")).strip()
        if keyword:
            normalized_entities["keyword"] = keyword
            filters.append(
                RequestFilter(
                    field="hbl_contact.hbl_contact_name",
                    op="contains",
                    value=keyword,
                )
            )
        if customer_name:
            normalized_entities["customer_name"] = customer_name
            filters.append(
                RequestFilter(
                    field="hbl_account.hbl_account_name",
                    op="contains",
                    value=customer_name,
                )
            )
        # keyword/customer_name có thể rỗng khi user muốn lấy toàn bộ danh sách contact.

    elif intent == "CONTACT_CREATE":
        contact_name = str(entities.get("contact_name", entities.get("name", entities.get("keyword", "")))).strip()
        if contact_name:
            normalized_entities["contact_name"] = contact_name
            normalized_entities["customer_name"] = str(entities.get("customer_name", "")).strip() or None
            normalized_entities["email"] = str(entities.get("email", "")).strip() or None
            normalized_entities["phone"] = str(entities.get("phone", "")).strip() or None
            normalized_entities["title"] = str(entities.get("title", "")).strip() or None
        else:
            unresolved.append("contact_name")

    elif intent == "CONTACT_COMPARE":
        pass

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
        # customer_name/status có thể rỗng khi user muốn lấy toàn bộ danh sách contract.

    elif intent == "CONTRACT_CREATE":
        contract_name = str(entities.get("contract_name", entities.get("name", entities.get("keyword", "")))).strip()
        if contract_name:
            normalized_entities["contract_name"] = contract_name
            normalized_entities["customer_name"] = str(entities.get("customer_name", "")).strip() or None
            normalized_entities["assignee_id"] = str(entities.get("assignee_id", "")).strip() or None
        else:
            unresolved.append("contract_name")

    elif intent == "CONTRACT_COMPARE":
        pass

    elif intent == "OPPORTUNITY_LIST":
        keyword = str(entities.get("keyword", "")).strip()
        customer_name = str(entities.get("customer_name", "")).strip()
        if keyword:
            normalized_entities["keyword"] = keyword
            filters.append(
                RequestFilter(
                    field="hbl_opportunities.hbl_opportunities_name",
                    op="contains",
                    value=keyword,
                )
            )
        if customer_name:
            normalized_entities["customer_name"] = customer_name
            filters.append(
                RequestFilter(
                    field="hbl_account.hbl_account_name",
                    op="contains",
                    value=customer_name,
                )
            )
        # keyword có thể rỗng khi user muốn lấy toàn bộ danh sách opportunity.

    elif intent == "OPPORTUNITY_CREATE":
        opportunity_name = str(entities.get("opportunity_name", entities.get("name", entities.get("keyword", "")))).strip()
        if opportunity_name:
            normalized_entities["opportunity_name"] = opportunity_name
            normalized_entities["customer_name"] = str(entities.get("customer_name", "")).strip() or None
            normalized_entities["owner_id"] = str(entities.get("owner_id", "")).strip() or None
            normalized_entities["estimated_value"] = entities.get("estimated_value")
        else:
            unresolved.append("opportunity_name")

    elif intent == "OPPORTUNITY_COMPARE":
        pass

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
