"""Chạy eval ma trận case trên planner metadata và ghi nhận tri thức."""

from __future__ import annotations
from dynamic_metadata.planner import plan_with_metadata

def run_eval(cases: list[dict]) -> dict:
    total = len(cases)
    if not total:
        return {"total_cases": 0, "tool_accuracy": 0.0}

    metrics = {
        "tool_ok": 0,
        "path_ok": 0,
        "choice_ok": 0,
        "knowledge_hit": 0,
        "entity_ok": 0,
    }
    rows: list[dict] = []

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
        decision = plan_with_metadata(state, knowledge_hits=knowledge_hits)
        trace = decision.get("trace", {})

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
            "knowledge_applied": is_knowledge_used
        })

    # 4. Trả về báo cáo chuẩn cho Matrix Gate đọc
    return {
        "total_cases": total,
        "tool_accuracy": metrics["tool_ok"] / total,
        "path_resolution_success": metrics["path_ok"] / total,
        "choice_constraint_success": metrics["choice_ok"] / total,
        "entity_match_rate": metrics["entity_ok"] / total,
        "correction_reuse_hit_rate": metrics["knowledge_hit"] / total,
        "rows": rows,
    }