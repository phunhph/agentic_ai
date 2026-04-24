from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v2.ingest.pubsub_ingress import publish_event
from v2.ingest.pubsub_worker import process_event
from v2.lifecycle import LIFECYCLE_STORE
from v2.service import run_v2_pipeline


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_detail_query() -> None:
    r = run_v2_pipeline("chi tiết account Demo Account 1", session_id="rg-detail", lang="vi")
    assert_true(r.get("decision_state") == "auto_execute", "detail query should auto_execute")
    assert_true(len(r.get("result", [])) >= 1, "detail query should return at least 1 row")
    resp = str(r.get("assistant_response", ""))
    assert_true("Chi tiết chính" in resp, "detail query should return detailed section")
    assert_true("Gợi ý khai thác tiếp theo" in resp, "single-record detail should suggest exploitation steps")


def test_followup_context() -> None:
    sid = "rg-followup"
    run_v2_pipeline("danh sách contact", session_id=sid, lang="vi")
    r = run_v2_pipeline("chỉ lấy contact có account là Demo Account 1", session_id=sid, lang="vi")
    assert_true(r.get("execution_plan", {}).get("root_table") == "hbl_contact", "follow-up root_table should stay hbl_contact")
    assert_true(len(r.get("result", [])) >= 1, "follow-up filter should return rows")


def test_event_lifecycle_ack() -> None:
    event = publish_event(
        {"goal": "chi tiết account Demo Account 1", "role": "DEFAULT", "session_id": "rg-evt", "lang": "vi"},
        ack_sla_ms=1500,
    )
    event_id = str(event.get("event_id", ""))
    assert_true(bool(event_id), "event_id should exist")
    assert_true(bool(event.get("ack", {}).get("ok")), "ack should be ok")
    assert_true(not bool(event.get("ack", {}).get("ack_sla_breached")), "ack SLA should not be breached")
    process_event(event_id, "chi tiết account Demo Account 1", "DEFAULT", "rg-evt", "vi")
    state = LIFECYCLE_STORE.get(event_id) or {}
    statuses = [str(x.get("status", "")) for x in state.get("lifecycle", [])]
    assert_true("queued" in statuses and "analyzing" in statuses and "processing" in statuses, "lifecycle should include queued/analyzing/processing")
    assert_true(str(state.get("status", "")) in {"done", "clarify"}, "final status should be done/clarify")


def test_tactician_and_firewall() -> None:
    r = run_v2_pipeline("chi tiết account Demo Account 1", role="JUNIOR", session_id="rg-tact", lang="vi")
    tact = r.get("tactician_payload", {})
    fw = r.get("learning_update", {}).get("firewall_event", {})
    assert_true(bool(tact.get("recommended_next_steps")), "tactician should provide next steps")
    assert_true(bool((tact.get("signals", {}) or {}).get("exact_match")), "tactician should mark exact_match for one-row detail")
    assert_true(str(fw.get("decision", "")) in {"allow", "quarantine", "reject"}, "firewall decision should be valid")
    assert_true(str(r.get("learning_update", {}).get("learning_phase", "")) == "phase_understanding_v2", "learning phase should be understanding-first")


def test_reasoning_vs_lean_integrity() -> None:
    query = "chi tiết account Demo Account 1"
    base = run_v2_pipeline(query, role="DEFAULT", session_id="rg-integrity-base", lang="vi")
    jr = run_v2_pipeline(query, role="JUNIOR", session_id="rg-integrity-jr", lang="vi")
    sr = run_v2_pipeline(query, role="SENIOR", session_id="rg-integrity-sr", lang="vi")

    base_state = base.get("decision_state")
    base_plan = base.get("reasoning_integrity", {}).get("plan_fingerprint")
    assert_true(base_state == jr.get("decision_state") == sr.get("decision_state"), "lean must not alter decision_state")
    assert_true(base_plan == jr.get("reasoning_integrity", {}).get("plan_fingerprint"), "lean must not alter execution plan (junior)")
    assert_true(base_plan == sr.get("reasoning_integrity", {}).get("plan_fingerprint"), "lean must not alter execution plan (senior)")
    assert_true(bool(jr.get("reasoning_integrity", {}).get("response_layers", {}).get("lean_changes_only_output")), "junior lean should only change output layer")
    assert_true(bool(sr.get("reasoning_integrity", {}).get("response_layers", {}).get("lean_changes_only_output")), "senior lean should only change output layer")


def test_aggregate_stats_query() -> None:
    q = "thống kê số lượng account, contract, và opp cùng với doanh thu hiện tại"
    r = run_v2_pipeline(q, session_id="rg-agg", lang="vi")
    assert_true(r.get("decision_state") == "auto_execute", "aggregate query should auto_execute")
    plan = r.get("execution_plan", {})
    agg = plan.get("aggregate_ops", []) if isinstance(plan, dict) else []
    assert_true(bool(agg), "aggregate query should compile aggregate ops")
    rows = r.get("result", []) if isinstance(r.get("result"), list) else []
    assert_true(len(rows) >= 1 and isinstance(rows[0], dict), "aggregate query should return metric row")
    keys = set(rows[0].keys())
    assert_true(any(k.endswith("_count") for k in keys), "aggregate result should include count metrics")


def main() -> None:
    test_detail_query()
    test_followup_context()
    test_event_lifecycle_ack()
    test_tactician_and_firewall()
    test_reasoning_vs_lean_integrity()
    test_aggregate_stats_query()
    print("Regression passed: v2 runtime core behaviors are healthy.")


if __name__ == "__main__":
    main()
