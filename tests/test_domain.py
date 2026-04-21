from core.domain import infer_domain, normalize_domain_key


def test_infer_domain_sales():
    assert infer_domain("lấy đơn pending") == "sales"


def test_infer_domain_inventory():
    assert infer_domain("thống kê tồn kho") == "inventory"


def test_normalize_domain_key():
    assert normalize_domain_key("sales") == "sales"
    assert normalize_domain_key("bogus") == "general"
