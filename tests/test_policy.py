from infra.policy import ROLE_TOOL_ALLOWLIST, is_tool_allowed


def test_admin_can_inventory_stats():
    ok, msg = is_tool_allowed("ADMIN", "get_account_overview")
    assert ok and msg == ""


def test_buyer_cannot_inventory_stats():
    ok, msg = is_tool_allowed("BUYER", "get_account_overview")
    assert not ok
    assert "get_account_overview" in msg or "không được phép" in msg.lower()


def test_allowlist_has_expected_keys():
    assert "ADMIN" in ROLE_TOOL_ALLOWLIST
    assert "BUYER" in ROLE_TOOL_ALLOWLIST
