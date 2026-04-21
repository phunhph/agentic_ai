from core.schemas import PlannerDecision


def test_planner_decision_defaults():
    d = PlannerDecision.model_validate({"tool": "search_products"})
    assert d.thought == "..."
    assert d.args == {}
