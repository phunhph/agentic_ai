import dynamic_metadata.eval_runner as eval_runner
import dynamic_metadata.planner as planner


def test_intent_fast_path_for_list_intent():
    ok, reason = planner._can_use_intent_fast_path(
        current_intent="CONTACT_LIST",
        intent_tool="list_contacts",
        entities={},
        keyword="",
    )
    assert ok is True
    assert reason == "list_intent_fast_path"


def test_intent_fast_path_requires_signal_for_non_list():
    ok, reason = planner._can_use_intent_fast_path(
        current_intent="CONTRACT_DETAIL",
        intent_tool="get_contract_details",
        entities={},
        keyword="",
    )
    assert ok is False
    assert reason == "insufficient_signal"


def test_cached_match_case_avoids_duplicate_calls(monkeypatch):
    planner._CASE_MATCH_CACHE.clear()
    calls = {"count": 0}

    def fake_match_case(goal: str):
        calls["count"] += 1
        return {"case": {"query": goal, "expected_tool": "list_accounts"}, "similarity": 1.0}

    monkeypatch.setattr(planner, "match_case", fake_match_case)
    first = planner._cached_match_case("abc")
    second = planner._cached_match_case("abc")

    assert first == second
    assert calls["count"] == 1


def test_run_eval_reports_strict_block_rate(monkeypatch):
    def fake_plan_with_metadata(state, knowledge_hits=None):
        goal = str(state.get("goal", ""))
        strict_blocked = "block" in goal
        return {
            "tool": "final_answer" if strict_blocked else "list_accounts",
            "args": {},
            "trace": {
                "strict_blocked": strict_blocked,
                "selected_entities": [],
                "choice_constraints": [],
            },
        }

    monkeypatch.setattr(eval_runner, "plan_with_metadata", fake_plan_with_metadata)

    report = eval_runner.run_eval(
        [
            {"query": "normal case", "expected_tool": "list_accounts"},
            {"query": "please block", "expected_tool": "final_answer"},
        ]
    )

    assert report["total_cases"] == 2
    assert report["tool_accuracy"] == 1.0
    assert report["strict_block_rate"] == 0.5
    assert report["latency_ms"]["p95"] >= report["latency_ms"]["p50"]


def test_resolve_decision_state_returns_ask_clarify():
    state, confidence, reason = planner._resolve_decision_state(
        strict_blocked=False,
        current_intent="UNKNOWN",
        mentioned_tables=[],
        entities={},
        knowledge_hits=[],
        case_similarity=0.1,
        case_success_ratio=0.0,
        calibrated_evidence_floor=0.45,
    )
    assert state == "ask_clarify"
    assert 0.0 <= confidence <= 1.0
    assert reason in {"low_signal_ambiguous_query", "low_evidence_without_learning_hit"}


def test_resolve_decision_state_returns_safe_block_when_strict_blocked():
    state, confidence, reason = planner._resolve_decision_state(
        strict_blocked=True,
        current_intent="CONTRACT_LIST",
        mentioned_tables=["hbl_contract"],
        entities={"contract_id": "abc"},
        knowledge_hits=[],
        case_similarity=0.9,
        case_success_ratio=1.0,
        calibrated_evidence_floor=0.25,
    )
    assert state == "safe_block"
    assert 0.0 <= confidence <= 1.0
    assert reason == "strict_learned_only_mode_blocked"


def test_compute_calibrated_evidence_floor_decreases_with_feedback():
    floor, details = planner._compute_calibrated_evidence_floor(
        knowledge_hits=[{"score": 0.8}, {"final_match_score": 0.9}],
        case_success_ratio=0.7,
    )
    assert floor < 0.45
    assert details["learning_bonus"] > 0
    assert details["case_bonus"] > 0


def test_estimate_planner_complexity_is_bounded():
    score = planner._estimate_planner_complexity(
        mentioned_tables=["a", "b", "c", "d", "e"],
        knowledge_hits=[{}, {}, {}, {}, {}],
        choice_constraints=[{}, {}, {}, {}, {}],
        join_path=[{}, {}, {}, {}, {}],
    )
    assert score == 16
