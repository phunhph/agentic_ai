from tools.tool_registry import build_call_args


def test_build_call_orders_normalizes_status():
    pos = build_call_args("list_contracts", {"status": "pending", "customer_name": None})
    assert pos[1] == "PENDING"


def test_build_call_orders_shipped():
    pos = build_call_args("list_contracts", {"status": "shipped", "customer_name": "A"})
    assert pos[1] == "SHIPPED"


def test_build_call_create_account_name_fallback():
    pos = build_call_args("create_account", {"account_name": "Demo A"})
    assert pos[0] == "Demo A"


def test_build_call_create_contact_name_fallback():
    pos = build_call_args("create_contact", {"name": "Contact Z", "customer_name": "Demo Account 1"})
    assert pos[0] == "Contact Z"
    assert pos[1] == "Demo Account 1"
