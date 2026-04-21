from tools.tool_registry import build_call_args


def test_build_call_orders_normalizes_status():
    pos = build_call_args("get_orders", {"status": "pending", "customer_name": None})
    assert pos[1] == "PENDING"


def test_build_call_orders_shipped():
    pos = build_call_args("get_orders", {"status": "shipped", "customer_name": "A"})
    assert pos[1] == "SHIPPED"
