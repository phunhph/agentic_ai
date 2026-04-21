from infra.schemas import PlannerDecision


def test_planner_decision_defaults():
    d = PlannerDecision.model_validate({"tool": "list_accounts"})
    assert d.thought == "..."
    assert d.args == {}
