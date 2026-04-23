from agent.orchestrator import _build_clarify_observation


def test_build_clarify_observation_for_ambiguous_reason():
    payload = _build_clarify_observation(
        "xem giúp tôi",
        {"decision_reason": "low_signal_ambiguous_query", "selected_entities": ["hbl_account"]},
    )
    assert payload["type"] == "ask_clarify"
    assert payload["reason"] == "low_signal_ambiguous_query"
    assert "accounts" in payload["message"]
    assert "hbl_account" in payload["message"]


def test_build_clarify_observation_has_default_reason():
    payload = _build_clarify_observation("xem giúp tôi", {})
    assert payload["type"] == "ask_clarify"
    assert payload["reason"] == "uncertain_planning"
    assert payload["original_query"] == "xem giúp tôi"
