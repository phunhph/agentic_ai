"""Heuristic domain (không gọi LLM) — dùng partition learning/memory theo nghiệp vụ."""


def infer_domain(goal: str) -> str:
    g = (goal or "").lower()
    if any(
        k in g
        for k in (
            "đơn",
            "order",
            "contract",
            "hợp đồng",
            "opportunity",
            "cơ hội",
            "contact",
            "liên hệ",
        )
    ):
        return "sales"
    if any(
        k in g
        for k in (
            "thống kê",
            "báo cáo",
            "account",
            "khách hàng",
            "danh sách khách",
        )
    ):
        return "inventory"
    return "general"


def normalize_domain_key(domain: str | None) -> str:
    d = (domain or "general").strip().lower()
    if not d:
        return "general"
    return d if d in {"sales", "inventory", "general"} else "general"
