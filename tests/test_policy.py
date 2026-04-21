from core.policy import is_tool_allowed, ROLE_TOOL_ALLOWLIST


def test_admin_can_inventory_stats():
    ok, msg = is_tool_allowed("ADMIN", "get_inventory_stats")
    assert ok and msg == ""


def test_buyer_cannot_inventory_stats():
    ok, msg = is_tool_allowed("BUYER", "get_inventory_stats")
    assert not ok
    assert "get_inventory_stats" in msg or "không được phép" in msg.lower()


def test_allowlist_has_expected_keys():
    assert "ADMIN" in ROLE_TOOL_ALLOWLIST
    assert "BUYER" in ROLE_TOOL_ALLOWLIST
