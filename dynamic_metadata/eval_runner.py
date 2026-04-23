"""Chạy eval ma trận case trên planner metadata và ghi nhận tri thức."""

from __future__ import annotations
import statistics
import time
from dynamic_metadata.planner import plan_with_metadata

def run_eval(cases: list[dict]) -> dict:
    total = len(cases)
    if not total:
        return {
            "total_cases": 0,
            "tool_accuracy": 0.0,
            "strict_block_rate": 0.0,
            "latency_ms": {"mean": 0.0, "p50": 0.0, "p95": 0.0},
        }

    metrics = {
        "tool_ok": 0,
        "path_ok": 0,
        "choice_ok": 0,
        "knowledge_hit": 0,
        "entity_ok": 0,
        "strict_blocked": 0,
        "auto_execute": 0,
        "ask_clarify": 0,
        "safe_block": 0,
    }
    rows: list[dict] = []
    latency_ms_samples: list[float] = []
    calibrated_floors: list[float] = []
    decision_reason_count: dict[str, int] = {}

    for case in cases:
        state_entities: dict = {}
        target_identities = case.get("target_identities", [])
        if isinstance(target_identities, list):
            for ident in target_identities:
                if not isinstance(ident, dict):
                    continue
                f = str(ident.get("field", "")).strip()
                ident_id = str(ident.get("id", "")).strip()
                if f and ident_id:
                    state_entities[f] = ident_id
        # 1. Giả lập state dựa trên Metadata context
        state = {
            "goal": case["query"], 
            "role": case.get("role", "BUYER"), 
            "history": [],
            "entities": state_entities,
            "bootstrap_learning": True,
        }
        knowledge_hits = case.get("knowledge_hits", [])
        
        # 2. Thực thi Planner động (Lớp Planning)
        start_time = time.perf_counter()
        decision = plan_with_metadata(state, knowledge_hits=knowledge_hits)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        latency_ms_samples.append(elapsed_ms)
        trace = decision.get("trace", {})
        is_strict_blocked = bool(trace.get("strict_blocked"))
        metrics["strict_blocked"] += int(is_strict_blocked)
        decision_state = str(trace.get("decision_state", "auto_execute")).strip() or "auto_execute"
        decision_reason = str(trace.get("decision_reason", "sufficient_signal")).strip() or "sufficient_signal"
        if decision_state in {"auto_execute", "ask_clarify", "safe_block"}:
            metrics[decision_state] += 1
        decision_reason_count[decision_reason] = decision_reason_count.get(decision_reason, 0) + 1
        try:
            calibrated_floors.append(float(trace.get("calibrated_evidence_floor", 0.0) or 0.0))
        except (TypeError, ValueError):
            pass

        # 3. Dynamic Validation (Lean Logic - So khớp dựa trên kỳ vọng của Case)
        # Kiểm tra Tool
        tool_match = decision.get("tool") == case.get("expected_tool")
        metrics["tool_ok"] += int(tool_match)

        # Kiểm tra Path (JOIN logic từ Metadata Graph)
        path_match = True
        expected_entities = case.get("expected_entities", [])
        if expected_entities:
            selected = trace.get("selected_entities", [])
            path_match = all(e in selected for e in expected_entities)
        metrics["path_ok"] += int(path_match)

        # Kiểm tra Choice Constraint (White-list filtering)
        choice_match = True
        expected_group = case.get("choice_group")
        if expected_group:
            constraints = trace.get("choice_constraints", [])
            choice_match = any(c.get("choice_group") == expected_group for c in constraints)
        metrics["choice_ok"] += int(choice_match)

        # Kiểm tra hiệu quả Tự học (Knowledge reuse)
        is_knowledge_used = bool(knowledge_hits and tool_match)
        metrics["knowledge_hit"] += int(is_knowledge_used)

        # Kiểm tra định danh entity (ID-first)
        entity_match = True
        target_identities = case.get("target_identities", [])
        if isinstance(target_identities, list) and target_identities:
            decided_args = decision.get("args", {}) if isinstance(decision.get("args"), dict) else {}
            for ident in target_identities:
                if not isinstance(ident, dict):
                    continue
                field = str(ident.get("field", "")).strip()
                expected_id = str(ident.get("id", "")).strip()
                if field and expected_id and str(decided_args.get(field, "")).strip() != expected_id:
                    entity_match = False
                    break
        metrics["entity_ok"] += int(entity_match)

        # Lưu log chi tiết cho lớp Learning phân tích sau này
        rows.append({
            "query": case["query"],
            "tool": decision.get("tool"),
            "expected_tool": case.get("expected_tool"),
            "success": tool_match and path_match and choice_match,
            "entity_match": entity_match,
            "trace": trace,
            "knowledge_applied": is_knowledge_used,
            "strict_blocked": is_strict_blocked,
            "decision_state": decision_state,
            "decision_reason": decision_reason,
            "latency_ms": round(elapsed_ms, 3),
        })

    sorted_samples = sorted(latency_ms_samples)
    p50_idx = int(0.5 * (len(sorted_samples) - 1))
    p95_idx = int(0.95 * (len(sorted_samples) - 1))

    # 4. Trả về báo cáo chuẩn cho Matrix Gate đọc
    return {
        "total_cases": total,
        "tool_accuracy": metrics["tool_ok"] / total,
        "path_resolution_success": metrics["path_ok"] / total,
        "choice_constraint_success": metrics["choice_ok"] / total,
        "entity_match_rate": metrics["entity_ok"] / total,
        "correction_reuse_hit_rate": metrics["knowledge_hit"] / total,
        "strict_block_rate": metrics["strict_blocked"] / total,
        "decision_state_rate": {
            "auto_execute": metrics["auto_execute"] / total,
            "ask_clarify": metrics["ask_clarify"] / total,
            "safe_block": metrics["safe_block"] / total,
        },
        "decision_reason_distribution": decision_reason_count,
        "avg_calibrated_evidence_floor": round((sum(calibrated_floors) / len(calibrated_floors)), 4)
        if calibrated_floors
        else 0.0,
        "latency_ms": {
            "mean": round(statistics.fmean(latency_ms_samples), 3),
            "p50": round(sorted_samples[p50_idx], 3),
            "p95": round(sorted_samples[p95_idx], 3),
        },
        "rows": rows,
    }