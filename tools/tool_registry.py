"""Registry tool tập trung + chuẩn hóa args trước khi gọi DB."""

from __future__ import annotations

from typing import Any

from tools.inventory_tool import get_account_overview, list_accounts
from tools.order_tool import get_contract_details, list_contracts


def _normalize_args(tool: str, args: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(args or {})
    if tool == "list_accounts" and not out.get("keyword"):
        out["keyword"] = out.get("customer_name") or out.get("name") or ""
    if tool == "list_contracts" and out.get("status") is not None:
        s = out["status"]
        if isinstance(s, str) and s.strip():
            out["status"] = s.strip().upper()
    if tool == "get_contract_details" and not out.get("contract_id"):
        out["contract_id"] = out.get("order_id")
    return out


def _args_list_accounts(args: dict[str, Any]) -> list[Any]:
    return [args.get("keyword", "")]


def _args_get_account_overview(args: dict[str, Any]) -> list[Any]:
    return []


def _args_list_contracts(args: dict[str, Any]) -> list[Any]:
    return [args.get("customer_name"), args.get("status")]


def _args_get_contract_details(args: dict[str, Any]) -> list[Any]:
    return [args.get("contract_id")]


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "list_accounts": {
        "func": list_accounts,
        "extract_args": _args_list_accounts,
        "description": "Lấy danh sách account, có thể lọc theo từ khóa",
    },
    "get_account_overview": {
        "func": get_account_overview,
        "extract_args": _args_get_account_overview,
        "description": "Thống kê tổng quan account",
    },
    "list_contracts": {
        "func": list_contracts,
        "extract_args": _args_list_contracts,
        "description": "Lấy danh sách hợp đồng",
    },
    "get_contract_details": {
        "func": get_contract_details,
        "extract_args": _args_get_contract_details,
        "description": "Lấy chi tiết hợp đồng theo ID",
    },
}


def build_call_args(tool: str, raw_args: dict[str, Any] | None) -> list[Any]:
    """Chuẩn hóa args rồi trả list positional cho hàm tool."""
    if tool not in TOOL_REGISTRY:
        return []
    normalized = _normalize_args(tool, raw_args)
    return TOOL_REGISTRY[tool]["extract_args"](normalized)
