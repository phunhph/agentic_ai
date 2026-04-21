"""Registry tool tập trung + chuẩn hóa args trước khi gọi DB."""

from __future__ import annotations

from typing import Any

from tools.inventory_tool import get_inventory_stats, search_products
from tools.order_tool import get_order_details, get_orders


def _normalize_args(tool: str, args: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(args or {})
    if tool == "search_products" and not out.get("keyword"):
        out["keyword"] = out.get("customer_name") or out.get("name") or ""
    if tool == "get_orders" and out.get("status") is not None:
        s = out["status"]
        if isinstance(s, str) and s.strip():
            out["status"] = s.strip().upper()
    return out


def _args_search_products(args: dict[str, Any]) -> list[Any]:
    return [args.get("keyword", "")]


def _args_get_inventory_stats(args: dict[str, Any]) -> list[Any]:
    return []


def _args_get_orders(args: dict[str, Any]) -> list[Any]:
    return [args.get("customer_name"), args.get("status")]


def _args_get_order_details(args: dict[str, Any]) -> list[Any]:
    return [args.get("order_id")]


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "search_products": {
        "func": search_products,
        "extract_args": _args_search_products,
        "description": "Tìm kiếm account theo từ khóa",
    },
    "get_inventory_stats": {
        "func": get_inventory_stats,
        "extract_args": _args_get_inventory_stats,
        "description": "Thống kê tổng quan account",
    },
    "get_orders": {
        "func": get_orders,
        "extract_args": _args_get_orders,
        "description": "Lấy danh sách hợp đồng",
    },
    "get_order_details": {
        "func": get_order_details,
        "extract_args": _args_get_order_details,
        "description": "Lấy chi tiết hợp đồng theo ID",
    },
}


def build_call_args(tool: str, raw_args: dict[str, Any] | None) -> list[Any]:
    """Chuẩn hóa args rồi trả list positional cho hàm tool."""
    if tool not in TOOL_REGISTRY:
        return []
    normalized = _normalize_args(tool, raw_args)
    return TOOL_REGISTRY[tool]["extract_args"](normalized)
