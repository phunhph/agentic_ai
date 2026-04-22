from storage.database import get_db
from storage.repositories.opportunity_repository import (
    compare_opportunity_stats,
    create_opportunity as repo_create_opportunity,
    list_opportunities_with_context,
)


def list_opportunities(keyword: str = "", customer_name: str | None = None):
    with get_db() as db:
        return list_opportunities_with_context(db, keyword=keyword, customer_name=customer_name)


def create_opportunity(
    opportunity_name: str,
    customer_name: str | None = None,
    owner_id: str | None = None,
    estimated_value: float | None = None,
):
    if not str(opportunity_name or "").strip():
        return [{"error": "opportunity_name is required"}]
    with get_db() as db:
        return [
            repo_create_opportunity(
                db,
                opportunity_name=opportunity_name,
                customer_name=customer_name,
                owner_id=owner_id,
                estimated_value=estimated_value,
            )
        ]


def compare_opportunity_stats_tool():
    with get_db() as db:
        return compare_opportunity_stats(db)


__all__ = ["list_opportunities", "create_opportunity", "compare_opportunity_stats_tool"]
