from __future__ import annotations

import sys
import json
import concurrent.futures
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


def _run_pipeline(query: str, *, role: str = "DEFAULT", session_id: str = "", lang: str = "vi", timeout_seconds: int = 20):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(run_v2_pipeline, query, role=role, session_id=session_id, lang=lang)
        return fut.result(timeout=max(1, int(timeout_seconds)))


def test_detail_query() -> None:
    r = _run_pipeline("chi tiết user PhuNH #", session_id="rg-detail", lang="vi")
    assert_true(r.get("decision_state") == "auto_execute", "detail query should auto_execute")
    assert_true(len(r.get("result", [])) >= 1, "detail query should return at least 1 row")
    resp = str(r.get("assistant_response", ""))
    assert_true("Chi tiết chính" in resp, "detail query should return detailed section")
    values = [str(v) for row in (r.get("result", []) or []) if isinstance(row, dict) for v in row.values()]
    assert_true(any("PhuNH" in value for value in values), "detail query should return the requested identity")


def test_followup_context() -> None:
    sid = "rg-followup"
    _run_pipeline("danh sách contact", session_id=sid, lang="vi")
    r = _run_pipeline("chỉ lấy contact có account là test impord lead acc", session_id=sid, lang="vi")
    assert_true(r.get("execution_plan", {}).get("root_table") == "hbl_contact", "follow-up root_table should stay hbl_contact")
    filters = r.get("execution_plan", {}).get("where_filters", [])
    assert_true(
        any(str(f.get("field", "")) == "hbl_account.hbl_account_name" for f in filters if isinstance(f, dict)),
        "follow-up filter should stay on the related account field",
    )


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
    r = _run_pipeline("chi tiết user PhuNH #", role="JUNIOR", session_id="rg-tact", lang="vi")
    tact = r.get("tactician_payload", {})
    fw = r.get("learning_update", {}).get("firewall_event", {})
    assert_true(bool(tact.get("recommended_next_steps")), "tactician should provide next steps")
    assert_true(bool((tact.get("signals", {}) or {}).get("exact_match")), "tactician should mark exact_match for one-row detail")
    assert_true(str(fw.get("decision", "")) in {"allow", "quarantine", "reject"}, "firewall decision should be valid")
    assert_true(str(r.get("learning_update", {}).get("learning_phase", "")) == "phase_understanding_v2", "learning phase should be understanding-first")


def test_reasoning_vs_lean_integrity() -> None:
    query = "chi tiết user PhuNH #"
    base = _run_pipeline(query, role="DEFAULT", session_id="rg-integrity-base", lang="vi")
    jr = _run_pipeline(query, role="JUNIOR", session_id="rg-integrity-jr", lang="vi")
    sr = _run_pipeline(query, role="SENIOR", session_id="rg-integrity-sr", lang="vi")

    base_state = base.get("decision_state")
    base_plan = base.get("reasoning_integrity", {}).get("plan_fingerprint")
    assert_true(base_state == jr.get("decision_state") == sr.get("decision_state"), "lean must not alter decision_state")
    assert_true(base_plan == jr.get("reasoning_integrity", {}).get("plan_fingerprint"), "lean must not alter execution plan (junior)")
    assert_true(base_plan == sr.get("reasoning_integrity", {}).get("plan_fingerprint"), "lean must not alter execution plan (senior)")
    jr_layers = jr.get("reasoning_integrity", {}).get("response_layers", {})
    sr_layers = sr.get("reasoning_integrity", {}).get("response_layers", {})
    assert_true("before_lean" in jr_layers and "after_lean" in jr_layers, "junior lean trace should include response layers")
    assert_true("before_lean" in sr_layers and "after_lean" in sr_layers, "senior lean trace should include response layers")


def test_aggregate_stats_query() -> None:
    q = "thống kê số lượng account, contract, và opp cùng với doanh thu hiện tại"
    r = _run_pipeline(q, session_id="rg-agg", lang="vi")
    assert_true(r.get("decision_state") == "auto_execute", "aggregate query should auto_execute")
    plan = r.get("execution_plan", {})
    agg = plan.get("aggregate_ops", []) if isinstance(plan, dict) else []
    assert_true(bool(agg), "aggregate query should compile aggregate ops")
    rows = r.get("result", []) if isinstance(r.get("result"), list) else []
    assert_true(len(rows) >= 1 and isinstance(rows[0], dict), "aggregate query should return metric row")
    keys = set(rows[0].keys())
    assert_true(any(k.endswith("_count") for k in keys), "aggregate result should include count metrics")


def test_aggregate_month_compare_query() -> None:
    q = "Thống kê Số lead mới được tạo ra, op mới được tạo ra trong tháng 3, và so với tháng 2, tháng 1 năm 2026"
    r = _run_pipeline(q, session_id="rg-agg-month-compare", lang="vi")
    assert_true(r.get("decision_state") == "auto_execute", "month compare aggregate query should auto_execute")
    plan = r.get("execution_plan", {})
    agg = plan.get("aggregate_ops", []) if isinstance(plan, dict) else []
    assert_true(bool(agg), "month compare query should compile aggregate ops")
    assert_true(
        any(str(op.get("alias", "")).endswith("2026_03") for op in agg if isinstance(op, dict)),
        "aggregate ops should include march 2026 metric",
    )
    assert_true(
        all(
            isinstance(op, dict)
            and any(str(f.get("field", "")).endswith(".createdon") for f in (op.get("filters", []) or []) if isinstance(f, dict))
            for op in agg
        ),
        "month compare aggregate filters should target createdon field",
    )


def test_detail_user_identity() -> None:
    r = _run_pipeline("chi tiết user PhuNH #", session_id="rg-user-identity", lang="vi")
    plan = r.get("execution_plan", {})
    filters = plan.get("where_filters", []) if isinstance(plan, dict) else []
    assert_true(plan.get("root_table") == "systemuser", "detail user query should route to systemuser")
    assert_true(bool(filters), "detail user query should compile exact identity filter")
    assert_true(
        all(str(f.get("field", "")) != "systemuser.address1_name" for f in filters if isinstance(f, dict)),
        "detail user query must not use address1_name as identity field",
    )
    assert_true(
        any(str(f.get("field", "")) == "systemuser.fullname" and str(f.get("op", "")) == "eq" for f in filters if isinstance(f, dict)),
        "detail user query should prefer fullname exact match",
    )


def test_compass_no_full_dump() -> None:
    r = _run_pipeline("có account nào tôi cần phải chăm sóc hôm nay không?", session_id="rg-compass", lang="vi")
    plan = r.get("execution_plan", {})
    tact = plan.get("tactical_context", {}) if isinstance(plan, dict) else {}
    frame = tact.get("intent_frame", {}) if isinstance(tact, dict) else {}
    assert_true(frame.get("reasoning_mode") == "compass_query", "compass query should select compass reasoning mode")
    assert_true(plan.get("root_table") == "hbl_account", "compass query should stay on account domain")
    assert_true(len(r.get("result", [])) == 0, "unsupported compass query should not dump full list")
    assert_true(
        "tieu chi can xu ly" in str(r.get("assistant_response", "")).lower(),
        "unsupported compass query should explain missing action criteria",
    )


def test_owner_scope_no_name_hallucination() -> None:
    r = _run_pipeline("contact nào Duong Cindy cần xử lý trong hôm nay", session_id="rg-owner-scope", lang="vi")
    plan = r.get("execution_plan", {})
    tact = plan.get("tactical_context", {}) if isinstance(plan, dict) else {}
    frame = tact.get("intent_frame", {}) if isinstance(tact, dict) else {}
    filters = plan.get("where_filters", []) if isinstance(plan, dict) else []
    assert_true(
        frame.get("reasoning_mode") in {"compass_query", "scoped_retrieval"},
        "owner scope query should use business reasoning mode",
    )
    assert_true(
        all(str(f.get("field", "")) != "hbl_contact.hbl_contact_name" for f in filters if isinstance(f, dict)),
        "owner scope query must not hallucinate contact_name as person filter",
    )


def test_followup_context_refine() -> None:
    sid = "rg-followup-refine"
    _run_pipeline("danh sách contact", session_id=sid, lang="vi")
    mid = _run_pipeline("chỉ lấy contact có account là Demo Account 1", session_id=sid, lang="vi")
    assert_true(mid.get("execution_plan", {}).get("root_table") == "hbl_contact", "filtered follow-up should stay on contact root")
    mid_filters = mid.get("execution_plan", {}).get("where_filters", [])
    assert_true(
        any(str(f.get("field", "")) == "hbl_account.hbl_account_name" for f in mid_filters if isinstance(f, dict)),
        "filtered follow-up should keep account filter on related table",
    )
    tail = _run_pipeline("thế có những tên nào", session_id=sid, lang="vi")
    assert_true(tail.get("execution_plan", {}).get("root_table") == "hbl_contact", "short follow-up should keep previous contact root")
    assert_true(
        not tail.get("execution_plan", {}).get("where_filters"),
        "list-style follow-up should not carry old identity filters",
    )


def test_generic_list_systemuser() -> None:
    r = _run_pipeline("trên CRM đang có user nào", session_id="rg-systemuser-list", lang="vi")
    plan = r.get("execution_plan", {})
    assert_true(plan.get("root_table") == "systemuser", "generic user list should route to systemuser")
    assert_true(len(r.get("result", [])) >= 1, "generic user list should return users")


def main() -> None:
    test_detail_query()
    test_followup_context()
    test_event_lifecycle_ack()
    test_tactician_and_firewall()
    test_reasoning_vs_lean_integrity()
    test_aggregate_stats_query()
    test_aggregate_month_compare_query()
    test_detail_user_identity()
    test_compass_no_full_dump()
    test_owner_scope_no_name_hallucination()
    test_followup_context_refine()
    test_generic_list_systemuser()
    print("Regression passed: v2 runtime core behaviors are healthy.")


if __name__ == "__main__":
    main()
