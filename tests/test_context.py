from core.context import build_context_key, ensure_context_id, normalize_role


def test_normalize_role_defaults_invalid():
    assert normalize_role(None) == "BUYER"
    assert normalize_role("admin") == "ADMIN"


def test_build_context_key_stable():
    s = ensure_context_id("sess-1")
    c = ensure_context_id("conv-1")
    k = build_context_key(s, "BUYER", c)
    assert k == f"BUYER:{s}:{c}"
