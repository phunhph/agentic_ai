"""Registry tool tập trung + chuẩn hóa args trước khi gọi DB."""

from __future__ import annotations

from typing import Any

from tools.modules import (
    compare_account_stats,
    compare_contact_stats_tool,
    compare_contract_stats_tool,
    create_account,
    create_contact,
    get_contact_details,
    create_contract_tool,
    create_opportunity,
    dynamic_query,
    get_account_360,
    get_account_overview,
    get_contract_details,
    list_accounts,
    list_contacts,
    list_contracts,
    list_opportunities,
    compare_opportunity_stats_tool,
)


def _normalize_args(tool: str, args: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(args or {})
    if tool == "list_accounts" and not out.get("keyword"):
        out["keyword"] = out.get("customer_name") or out.get("name") or ""
    if tool == "list_contacts" and not out.get("customer_name"):
        maybe_customer = out.get("account_name") or out.get("customer") or out.get("account")
        if isinstance(maybe_customer, str) and maybe_customer.strip():
            out["customer_name"] = maybe_customer.strip()
    if tool == "list_contracts" and out.get("status") is not None:
        s = out["status"]
        if isinstance(s, str) and s.strip():
            out["status"] = s.strip().upper()
    if tool == "get_contract_details" and not out.get("contract_id"):
        out["contract_id"] = out.get("order_id")
    if tool == "create_account" and not out.get("name"):
        out["name"] = out.get("account_name") or out.get("customer_name") or out.get("keyword") or ""
    if tool == "create_contact" and not out.get("contact_name"):
        out["contact_name"] = out.get("name") or out.get("keyword") or ""
    if tool == "create_contract" and not out.get("contract_name"):
        out["contract_name"] = out.get("name") or out.get("keyword") or ""
    if tool == "create_opportunity" and not out.get("opportunity_name"):
        out["opportunity_name"] = out.get("name") or out.get("keyword") or ""
    return out


def _args_list_accounts(args: dict[str, Any]) -> list[Any]:
    return [args.get("keyword", ""), args.get("bd_owner_id"), args.get("am_sales_id")]


def _args_get_account_overview(args: dict[str, Any]) -> list[Any]:
    return []


def _args_get_account_360(args: dict[str, Any]) -> list[Any]:
    return [args.get("keyword", "")]


def _args_create_account(args: dict[str, Any]) -> list[Any]:
    return [
        args.get("name", ""),
        args.get("website"),
        args.get("domain"),
        args.get("bd_owner_id"),
        args.get("am_sales_id"),
    ]


def _args_compare_account_stats(args: dict[str, Any]) -> list[Any]:
    return []


def _args_list_contacts(args: dict[str, Any]) -> list[Any]:
    return [args.get("keyword", ""), args.get("customer_name")]


def _args_create_contact(args: dict[str, Any]) -> list[Any]:
    return [
        args.get("contact_name", ""),
        args.get("customer_name"),
        args.get("email"),
        args.get("phone"),
        args.get("title"),
    ]


def _args_get_contact_details(args: dict[str, Any]) -> list[Any]:
    return [args.get("contact_id"), args.get("keyword")]


def _args_compare_contact_stats(args: dict[str, Any]) -> list[Any]:
    return []


def _args_list_contracts(args: dict[str, Any]) -> list[Any]:
    return [args.get("customer_name"), args.get("status")]


def _args_create_contract(args: dict[str, Any]) -> list[Any]:
    return [args.get("contract_name", ""), args.get("customer_name"), args.get("assignee_id")]


def _args_compare_contract_stats(args: dict[str, Any]) -> list[Any]:
    return []


def _args_get_contract_details(args: dict[str, Any]) -> list[Any]:
    return [args.get("contract_id")]


def _args_list_opportunities(args: dict[str, Any]) -> list[Any]:
    return [args.get("keyword", ""), args.get("customer_name")]


def _args_create_opportunity(args: dict[str, Any]) -> list[Any]:
    return [
        args.get("opportunity_name", ""),
        args.get("customer_name"),
        args.get("owner_id"),
        args.get("estimated_value"),
    ]


def _args_compare_opportunity_stats(args: dict[str, Any]) -> list[Any]:
    return []


def _args_dynamic_query(args: dict[str, Any]) -> list[Any]:
    return [
        {
            "root_table": args.get("root_table", "hbl_account"),
            "keyword": args.get("keyword", ""),
            "include_tables": args.get("include_tables") if isinstance(args.get("include_tables"), list) else [],
            "limit": args.get("limit", 20),
            "id_filters": args.get("id_filters") if isinstance(args.get("id_filters"), dict) else {},
            "filters": args.get("filters") if isinstance(args.get("filters"), list) else [],
        }
    ]


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "list_accounts": {
        "func": list_accounts,
        "extract_args": _args_list_accounts,
        "description": "Lấy danh sách account, có thể lọc theo từ khóa",
        "arg_hints": ["keyword", "bd_owner_id", "am_sales_id"],
        "output_fields": ["id", "name", "website", "domain", "am_sales", "bd_owner", "contact_count", "opportunity_count", "contract_count"],
    },
    "get_account_overview": {
        "func": get_account_overview,
        "extract_args": _args_get_account_overview,
        "description": "Thống kê tổng quan account",
        "arg_hints": [],
        "output_fields": ["category", "account_count", "total_records"],
    },
    "get_account_360": {
        "func": get_account_360,
        "extract_args": _args_get_account_360,
        "description": "Lấy hồ sơ account đầy đủ gồm contacts, opportunities và contracts liên quan",
        "arg_hints": ["keyword"],
        "output_fields": ["account", "contacts", "opportunities", "contracts", "summary"],
    },
    "create_account": {
        "func": create_account,
        "extract_args": _args_create_account,
        "description": "Tạo mới account theo dữ liệu cung cấp",
        "arg_hints": ["name", "website", "domain", "bd_owner_id", "am_sales_id"],
        "output_fields": ["id", "name", "website", "domain", "bd_owner_id", "am_sales_id", "created", "error"],
    },
    "compare_account_stats": {
        "func": compare_account_stats,
        "extract_args": _args_compare_account_stats,
        "description": "Thống kê so sánh số lượng account theo owner",
        "arg_hints": [],
        "output_fields": ["owner_id", "owner_name", "account_count", "total_it_budget"],
    },
    "list_contacts": {
        "func": list_contacts,
        "extract_args": _args_list_contacts,
        "description": "Lấy danh sách liên hệ, có thể lọc theo từ khóa và account/customer",
        "arg_hints": ["keyword", "customer_name"],
        "output_fields": ["contact_id", "contact_name", "title", "email", "phone", "customer", "assignee", "next_action_date"],
    },
    "get_contact_details": {
        "func": get_contact_details,
        "extract_args": _args_get_contact_details,
        "description": "Lấy chi tiết contact theo ID hoặc từ khóa",
        "arg_hints": ["contact_id", "keyword"],
        "output_fields": ["contact_id", "contact_name", "title", "email", "phone", "customer", "assignee", "next_action_date", "meta"],
    },
    "create_contact": {
        "func": create_contact,
        "extract_args": _args_create_contact,
        "description": "Tạo mới liên hệ theo dữ liệu cung cấp",
        "arg_hints": ["contact_name", "customer_name", "email", "phone", "title"],
        "output_fields": ["contact_id", "contact_name", "email", "phone", "title", "customer_name", "created", "error"],
    },
    "compare_contact_stats": {
        "func": compare_contact_stats_tool,
        "extract_args": _args_compare_contact_stats,
        "description": "Thống kê so sánh số lượng contact theo assignee",
        "arg_hints": [],
        "output_fields": ["assignee_id", "assignee_name", "contact_count"],
    },
    "list_contracts": {
        "func": list_contracts,
        "extract_args": _args_list_contracts,
        "description": "Lấy danh sách hợp đồng",
        "arg_hints": ["customer_name", "status"],
        "output_fields": ["contract_name", "contract_id", "customer", "opportunity", "assignee", "status", "total", "date"],
    },
    "create_contract": {
        "func": create_contract_tool,
        "extract_args": _args_create_contract,
        "description": "Tạo mới hợp đồng theo dữ liệu cung cấp",
        "arg_hints": ["contract_name", "customer_name", "assignee_id"],
        "output_fields": ["contract_id", "contract_name", "customer_name", "assignee_id", "created", "error"],
    },
    "compare_contract_stats": {
        "func": compare_contract_stats_tool,
        "extract_args": _args_compare_contract_stats,
        "description": "Thống kê so sánh số lượng và giá trị contract theo assignee",
        "arg_hints": [],
        "output_fields": ["assignee_id", "assignee_name", "contract_count", "total_contract_value"],
    },
    "get_contract_details": {
        "func": get_contract_details,
        "extract_args": _args_get_contract_details,
        "description": "Lấy chi tiết hợp đồng theo ID",
        "arg_hints": ["contract_id"],
        "output_fields": ["contract_id", "customer", "status", "items", "meta"],
    },
    "list_opportunities": {
        "func": list_opportunities,
        "extract_args": _args_list_opportunities,
        "description": "Lấy danh sách cơ hội bán hàng",
        "arg_hints": ["keyword", "customer_name"],
        "output_fields": ["opportunity_id", "opportunity_name", "customer", "owner", "estimated_value", "contract_count", "deadline"],
    },
    "create_opportunity": {
        "func": create_opportunity,
        "extract_args": _args_create_opportunity,
        "description": "Tạo mới cơ hội bán hàng",
        "arg_hints": ["opportunity_name", "customer_name", "owner_id", "estimated_value"],
        "output_fields": ["opportunity_id", "opportunity_name", "customer_name", "owner_id", "estimated_value", "created", "error"],
    },
    "compare_opportunity_stats": {
        "func": compare_opportunity_stats_tool,
        "extract_args": _args_compare_opportunity_stats,
        "description": "Thống kê so sánh cơ hội theo owner",
        "arg_hints": [],
        "output_fields": ["owner_id", "owner_name", "opportunity_count", "total_estimated_value"],
    },
    "dynamic_query": {
        "func": dynamic_query,
        "extract_args": _args_dynamic_query,
        "description": "Truy vấn động theo metadata với root table và các bảng liên quan",
        "arg_hints": ["root_table", "keyword", "include_tables", "limit"],
        "output_fields": ["root_table", "root_records", "related_records", "plan", "error"],
    },
}


def build_call_args(tool: str, raw_args: dict[str, Any] | None) -> list[Any]:
    """Chuẩn hóa args rồi trả list positional cho hàm tool."""
    if tool not in TOOL_REGISTRY:
        return []
    normalized = _normalize_args(tool, raw_args)
    return TOOL_REGISTRY[tool]["extract_args"](normalized)
