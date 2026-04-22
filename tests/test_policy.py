from infra.policy import ROLE_TOOL_ALLOWLIST, is_tool_allowed


def test_single_role_allows_overview():
    ok, msg = is_tool_allowed("ADMIN", "get_account_overview")
    assert ok and msg == ""


def test_single_role_allows_create_and_compare():
    ok_create, _ = is_tool_allowed("BUYER", "create_account")
    ok_compare, _ = is_tool_allowed("BUYER", "compare_account_stats")
    assert ok_create and ok_compare


def test_allowlist_has_default_role_only():
    assert "DEFAULT" in ROLE_TOOL_ALLOWLIST
