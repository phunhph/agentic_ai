"""Heuristic domain (không gọi LLM) — dùng partition learning/memory theo nghiệp vụ."""


def infer_domain(goal: str) -> str:
    g = (goal or "").lower()
    if any(k in g for k in ("đơn", "order", "pending", "shipped", "delivered", "khách")):
        return "sales"
    if any(
        k in g
        for k in (
            "tồn kho",
            "thống kê",
            "báo cáo",
            "inventory",
            "sku",
            "danh mục",
        )
    ):
        return "inventory"
    return "general"


def normalize_domain_key(domain: str | None) -> str:
    d = (domain or "general").strip().lower()
    if not d:
        return "general"
    return d if d in {"sales", "inventory", "general"} else "general"
