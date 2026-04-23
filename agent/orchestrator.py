import json
import asyncio
import re
from typing import AsyncGenerator
from agent.brain import agent_brain
from agent.dynamic_planner import plan_with_metadata
from agent.perception import perception_node
from agent.field_resolver import INTENT_TOOL_HINT
from dynamic_metadata.matrix_gate import evaluate_matrix_gate
from agent.action import action_node
from agent.evaluator import evaluator_node
from memory.learning import AgentLearning
from memory.manager import AgentMemory
from infra.context import normalize_role, ensure_context_id, build_context_key
from infra.domain import infer_domain, normalize_domain_key
from infra.policy import is_tool_allowed
from infra.settings import (
    ENABLE_DYNAMIC_METADATA_PLANNER,
    ENABLE_MATRIX_IO_TRACE,
    ENABLE_TRACE_TOKEN_STATS,
    AUTO_MATRIX_EVAL_REFRESH,
    AUTO_MATRIX_LEARNING,
    MATRIX_ALLOWED_TOOLS,
    MATRIX_KNOWLEDGE_HITS_LIMIT,
)
from dynamic_metadata.matrix_learning import penalize_case, refresh_matrix_eval_report, upsert_case_from_run
from dynamic_metadata.trace_metrics import estimate_tokens
from storage.database import SessionLocal
from storage.repositories.knowledge_repository import (
    find_similar_lessons,
    mark_lessons_outcome,
    penalize_lessons,
    prune_low_confidence_lessons,
    record_correction,
)


def _build_clarify_observation(query_text: str, trace: dict) -> dict:
    reason = str((trace or {}).get("decision_reason", "")).strip()
    entities = (trace or {}).get("selected_entities", [])
    entity_hint = ", ".join([str(x) for x in entities[:2]]) if isinstance(entities, list) else ""
    if reason == "low_signal_ambiguous_query":
        question = "Bạn muốn xem dữ liệu nào cụ thể hơn (accounts, contacts, contracts hay opportunities)?"
    elif reason == "low_evidence_without_learning_hit":
        question = "Bạn vui lòng bổ sung thêm điều kiện (ví dụ tên khách hàng, assignee hoặc mã contract) để mình truy vấn chính xác."
    else:
        question = "Bạn vui lòng làm rõ mục tiêu truy vấn để mình chọn đúng công cụ."
    if entity_hint:
        question = f"{question} (Tín hiệu hiện có: {entity_hint})"
    return {
        "type": "ask_clarify",
        "message": question,
        "reason": reason or "uncertain_planning",
        "original_query": query_text,
    }


class AgentOrchestrator:
    def __init__(self):
        self.memory = AgentMemory()
        self.learning = AgentLearning()

    def ingest_feedback(self, feedback: dict) -> str | None:
        if not isinstance(feedback, dict):
            return None
        original_query = str(feedback.get("original_query", "")).strip()
        correction_text = str(feedback.get("correction_text", "")).strip()
        if not original_query or not correction_text:
            return None
        db = SessionLocal()
        try:
            row = record_correction(
                db,
                context_key=str(feedback.get("context_key", "")).strip() or None,
                user_role=str(feedback.get("role", "DEFAULT")).strip() or "DEFAULT",
                domain=str(feedback.get("domain", "general")).strip() or "general",
                original_query=original_query,
                wrong_answer_excerpt=str(feedback.get("wrong_answer_excerpt", "")).strip() or None,
                correction_text=correction_text,
                error_type=str(feedback.get("error_type", "explicit_feedback")).strip() or "explicit_feedback",
                resolved_intent=str(feedback.get("resolved_intent", "")).strip() or None,
                resolved_entities=feedback.get("resolved_entities") if isinstance(feedback.get("resolved_entities"), dict) else {},
            )
            return row.id
        finally:
            db.close()

    async def run(
        self,
        goal: str,
        role: str = "DEFAULT",
        history: str = "[]",
        session_id: str = "",
        conversation_id: str = "",
    ) -> AsyncGenerator[str, None]:
        session_role = normalize_role(role)
        current_session_id = ensure_context_id(session_id)
        current_conversation_id = ensure_context_id(conversation_id)
        context_key = build_context_key(
            current_session_id, session_role, current_conversation_id
        )

        async def emit_log(block: str, content: str, status: str = "INFO"):
            payload = {
                "type": "log",
                "log": {
                    "block": block,
                    "content": content,
                    "status": status,
                    "role": session_role,
                    "session_id": current_session_id,
                    "conversation_id": current_conversation_id,
                    "context_key": context_key,
                },
            }
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # Parse history
        try:
            chat_history = json.loads(history)
        except Exception:
            chat_history = []
        matrix_gate_passed, matrix_gate_info = evaluate_matrix_gate()
        stage_token_stats: dict[str, dict] = {}

        def maybe_record_correction(query_text: str, role: str, domain: str) -> None:
            normalized = (query_text or "").strip().lower()
            correction_markers = (
                "kiểm tra lại",
                "check lại",
                "tháng",
                "năm",
                "ý tôi",
                "sai rồi",
                "nhé",
                "lần sau",
            )
            if not any(m in normalized for m in correction_markers):
                return
            if not chat_history:
                return
            previous = chat_history[-1]
            original_query = str(previous.get("goal", "")).strip() or query_text
            wrong_answer = str(previous.get("result", ""))[:500]
            db = SessionLocal()
            try:
                record_correction(
                    db,
                    context_key=context_key,
                    user_role=role,
                    domain=domain,
                    original_query=original_query,
                    wrong_answer_excerpt=wrong_answer,
                    correction_text=query_text,
                    error_type="user_correction",
                    resolved_intent=None,
                    resolved_entities={},
                )
            finally:
                db.close()

        def check_entity_match(entities: dict, observations: list[dict]) -> tuple[bool, str]:
            if not isinstance(observations, list) or not observations:
                return True, ""
            if not isinstance(request_contract, dict):
                return True, ""
            filters = request_contract.get("filters", [])
            if not isinstance(filters, list) or not filters:
                return True, ""

            def _norm_tokens(text: str) -> set[str]:
                raw = re.sub(r"[^a-zA-Z0-9_]+", " ", str(text or "").lower()).strip()
                toks = [t for t in raw.split() if t]
                cleaned: list[str] = []
                for t in toks:
                    t = re.sub(r"^(hbl|mc|cr\d+)_", "", t)
                    if t in {"account", "contact", "contract", "opportunities", "opportunity"}:
                        continue
                    cleaned.append(t)
                return set(cleaned)

            def _resolve_output_key(filter_field: str, row: dict) -> str | None:
                if not isinstance(row, dict) or not row:
                    return None
                col = str(filter_field).split(".", 1)[-1]
                col_tokens = _norm_tokens(col)
                best_key = None
                best_score = -1
                for key in row.keys():
                    key_tokens = _norm_tokens(str(key))
                    score = len(col_tokens.intersection(key_tokens))
                    if score > best_score:
                        best_score = score
                        best_key = str(key)
                return best_key if best_score > 0 else None

            for f in filters:
                if not isinstance(f, dict):
                    continue
                field = str(f.get("field", "")).strip()
                op = str(f.get("op", "contains")).strip().lower()
                expected = str(f.get("value", "")).strip().lower()
                if not field or not expected:
                    continue
                for row in observations:
                    if not isinstance(row, dict):
                        continue
                    out_key = _resolve_output_key(field, row)
                    if not out_key:
                        continue
                    actual = str(row.get(out_key, "")).strip().lower()
                    if op == "eq" and actual != expected:
                        return False, f"filter_mismatch:{field}:eq"
                    if op == "contains" and expected not in actual:
                        return False, f"filter_mismatch:{field}:contains"
            return True, ""

        # 1. PERCEPTION
        yield await emit_log("TRACE", f"INPUT [Goal]: {goal}", "RECEIVING")
        perception_result = perception_node({"goal": goal, "role": session_role})
        
        clean_goal = perception_result["goal"]
        planner_goal = perception_result.get("planner_goal", clean_goal)
        detected_role = perception_result.get("role", role)
        intent = perception_result.get("intent", "UNKNOWN")
        entities = perception_result.get("entities", {})
        request_contract = perception_result.get("request_contract", {})
        perception_trace = perception_result.get("trace", {})
        domain = normalize_domain_key(infer_domain(clean_goal))
        maybe_record_correction(clean_goal, detected_role, domain)
        if ENABLE_TRACE_TOKEN_STATS:
            stage_token_stats["perceive"] = {
                "input_tokens_est": estimate_tokens(goal),
                "output_tokens_est": estimate_tokens(
                    {
                        "goal": clean_goal,
                        "planner_goal": planner_goal,
                        "intent": intent,
                        "entities": entities,
                    }
                ),
            }

        yield await emit_log(
            "PERCEIVE",
            (
                f'OUTPUT: Goal="{clean_goal}" | PlannerGoal="{planner_goal}" | '
                f"Intent={intent} | Entities={json.dumps(entities, ensure_ascii=False)} | "
                f"ContractValid={request_contract.get('valid', True)} | "
                f"Role={detected_role} | Domain={domain}"
            ),
            "DONE",
        )
        await asyncio.sleep(0)

        # STATE
        state = {
            "goal": planner_goal,
            "raw_goal": clean_goal,
            "role": detected_role,
            "domain": domain,
            "intent": intent,
            "entities": entities,
            "request_contract": request_contract,
            "session_id": current_session_id,
            "conversation_id": current_conversation_id,
            "context_key": context_key,
            "history": chat_history,
            "is_finished": False,
            "iteration": 0,
            "steps": [],
            "observations": [],
            "selected_tool": "",
            "selected_args": {},
            "db_call_executed": False,
            "entity_match_ok": True,
            "entity_match_reason": "",
            "entity_extract": perception_result.get("entity_extract", {}),
        }
        state["bootstrap_learning"] = self.learning.lesson_count(detected_role, domain) == 0

        while not state["is_finished"] and state["iteration"] < 5:
            state["iteration"] += 1
            yield await emit_log("TRACE", f"--- ITERATION {state['iteration']} ---", "START")

            # 2. PLANNING (BRAIN)
            yield await emit_log("REASON", f"INPUT [Context]: Goal + Memory + RAG", "PROCESSING")
            matrix_trace_io = {}
            if ENABLE_DYNAMIC_METADATA_PLANNER and matrix_gate_passed:
                db = SessionLocal()
                try:
                    lessons = find_similar_lessons(
                        db,
                        query=state.get("goal", ""),
                        role=detected_role,
                        domain=domain,
                        limit=MATRIX_KNOWLEDGE_HITS_LIMIT,
                        query_intent=str(state.get("intent", "")),
                        query_entities=state.get("entities", {}) if isinstance(state.get("entities"), dict) else {},
                    )
                finally:
                    db.close()
                matrix_input = {
                    "goal": state.get("goal", ""),
                    "role": detected_role,
                    "domain": domain,
                    "knowledge_hits_count": len(lessons),
                    "knowledge_hits_preview": lessons[:2],
                }
                decision = plan_with_metadata(state, knowledge_hits=lessons)
                matrix_output = {
                    "thought": decision.get("thought"),
                    "tool": decision.get("tool"),
                    "args": decision.get("args", {}),
                    "trace": decision.get("trace", {}),
                }
                if ENABLE_MATRIX_IO_TRACE:
                    matrix_trace_io = {
                        "matrix_input": matrix_input,
                        "matrix_output": matrix_output,
                    }
                if ENABLE_TRACE_TOKEN_STATS:
                    stage_token_stats["matrix"] = {
                        "input_tokens_est": estimate_tokens(matrix_input),
                        "output_tokens_est": estimate_tokens(matrix_output),
                    }
                state["knowledge_hit_ids"] = [str(x.get("id")) for x in lessons if x.get("id")]
                decision.setdefault("trace", {})
                decision["trace"]["matrix_gate"] = matrix_gate_info
                if decision.get("tool") not in MATRIX_ALLOWED_TOOLS:
                    fallback_tool = INTENT_TOOL_HINT.get(str(state.get("intent", "")).upper(), "final_answer")
                    if fallback_tool not in MATRIX_ALLOWED_TOOLS:
                        fallback_tool = "final_answer"
                    decision = {
                        "thought": "Matrix trả tool không hợp lệ; fallback theo intent mapping để tránh drift từ legacy brain.",
                        "tool": fallback_tool,
                        "args": {},
                        "trace": {
                            "fallback_reason": "dynamic planner tool mismatch; fallback intent-mapped",
                            "matrix_gate": matrix_gate_info,
                        },
                    }
            else:
                decision = agent_brain(state)
                decision.setdefault("trace", {})
                if ENABLE_DYNAMIC_METADATA_PLANNER and not matrix_gate_passed:
                    decision["trace"]["fallback_reason"] = "matrix gate not passed; use legacy planner"
                decision["trace"]["matrix_gate"] = matrix_gate_info
            
            thought = decision.get("thought", "...")
            tool = decision.get("tool", "error")
            args = decision.get("args", {})
            trace = decision.get("trace", {})
            if not isinstance(trace, dict):
                trace = {}
            if matrix_trace_io:
                trace.update(matrix_trace_io)
            if ENABLE_TRACE_TOKEN_STATS:
                stage_token_stats["reason"] = {
                    "input_tokens_est": estimate_tokens(
                        {
                            "goal": state.get("goal"),
                            "history_tail": state.get("history", [])[-3:],
                            "observations": state.get("observations", []),
                        }
                    ),
                    "output_tokens_est": estimate_tokens(
                        {
                            "thought": thought,
                            "tool": tool,
                            "args": args,
                            "trace_keys": sorted(list(trace.keys())),
                        }
                    ),
                }
            state["planner_trace"] = trace
            state["selected_tool"] = tool
            state["selected_args"] = args

            yield await emit_log(
                "REASON", 
                f"OUTPUT [Decision]: Thought='{thought}' | Tool='{tool}' | Args={json.dumps(args, ensure_ascii=False)}", 
                "DECIDED"
            )
            await asyncio.sleep(0)
            
            yield await emit_log(
                "LEARN",
                (
                    f"TRACE [Knowledge]: Recall='{trace.get('past_experience', 'N/A')}' | "
                    f"Entities={json.dumps(trace.get('selected_entities', []), ensure_ascii=False)} | "
                    f"JoinPath={json.dumps(trace.get('join_path', []), ensure_ascii=False)} | "
                    f"ChoiceConstraints={json.dumps(trace.get('choice_constraints', []), ensure_ascii=False)} | "
                    f"KnowledgeHits={len(trace.get('knowledge_hits', []) or [])} | "
                    f"Fallback='{trace.get('fallback_reason', '')}' | "
                    f"MatrixGate={json.dumps(trace.get('matrix_gate', matrix_gate_info), ensure_ascii=False)}"
                ),
                "MEMORY"
            )
            if trace.get("strict_blocked"):
                yield await emit_log("POLICY", f"STRICT_LEARNED_ONLY: {trace.get('strict_reason', 'blocked')}", "BLOCKED")

            if trace.get("decision_state") == "ask_clarify":
                clarify_observation = _build_clarify_observation(clean_goal, trace)
                state["observations"] = [clarify_observation]
                state["selected_tool"] = "final_answer"
                state["selected_args"] = {}
                state["is_finished"] = True
                yield await emit_log(
                    "POLICY",
                    f"ASK_CLARIFY: {clarify_observation.get('message', '')}",
                    "CLARIFY",
                )
                break

            if tool not in ("final_answer", "error"):
                allowed, deny_reason = is_tool_allowed(detected_role, tool)
                if not allowed:
                    yield await emit_log("POLICY", f"DENIED: {deny_reason}", "BLOCK")
                    state["observations"] = []
                    eval_result = evaluator_node(state)
                    state["is_finished"] = eval_result.get("is_finished", False)
                    continue

            if tool == "final_answer":
                state["is_finished"] = True
                self.memory.save_experience(clean_goal, "completed", len(state["observations"]), context_key=context_key)
                yield await emit_log("EVAL", "OUTPUT: Hoàn tất với dữ liệu hiện có.", "DONE")
                break

            if tool == "error":
                state["is_finished"] = True
                yield await emit_log("EVAL", "OUTPUT: Thất bại (Lỗi suy luận).", "FAILED")
                break

            # 3. EXECUTION (ACTION)
            yield await emit_log("ACT", f"INPUT [Action]: Tool='{tool}' | Args={json.dumps(args, ensure_ascii=False)}", "EXECUTING")
            state["next_action"] = tool
            state["next_args"] = args
            state["db_call_executed"] = True
            act_res = action_node(state)
            
            state["observations"] = act_res["observations"]
            if ENABLE_TRACE_TOKEN_STATS:
                stage_token_stats["act"] = {
                    "input_tokens_est": estimate_tokens({"tool": tool, "args": args}),
                    "output_tokens_est": estimate_tokens(state["observations"]),
                }
            
            yield await emit_log(
                "ACT", 
                f"OUTPUT [Obs]: Tìm thấy {len(state['observations'])} bản ghi.", 
                "SUCCESS" if state["observations"] else "NOT_FOUND"
            )
            if ENABLE_DYNAMIC_METADATA_PLANNER and state.get("knowledge_hit_ids"):
                db = SessionLocal()
                try:
                    mark_lessons_outcome(
                        db,
                        state.get("knowledge_hit_ids", []),
                        success=bool(state["observations"]),
                    )
                finally:
                    db.close()

            entity_match_ok, entity_mismatch_reason = check_entity_match(entities, state["observations"])
            state["entity_match_ok"] = entity_match_ok
            state["entity_match_reason"] = entity_mismatch_reason
            if not entity_match_ok and state.get("knowledge_hit_ids"):
                db = SessionLocal()
                try:
                    penalize_lessons(
                        db,
                        state.get("knowledge_hit_ids", []),
                        penalty=0.3,
                    )
                    pruned = prune_low_confidence_lessons(
                        db,
                        role=detected_role,
                        domain=domain,
                        keep_top=30,
                    )
                finally:
                    db.close()
                yield await emit_log(
                    "LEARN",
                    f"NEGATIVE REINFORCEMENT: {entity_mismatch_reason}, penalized={len(state.get('knowledge_hit_ids', []))}, pruned={pruned}",
                    "DOWNGRADED",
                )

            if AUTO_MATRIX_LEARNING and tool in MATRIX_ALLOWED_TOOLS and tool not in {"final_answer", "error"}:
                try:
                    if not entity_match_ok:
                        penalize_case(clean_goal, amount=1)
                    matrix_update = upsert_case_from_run(
                        query=clean_goal,
                        expected_tool=tool,
                        trace=trace,
                        success=bool(state["observations"]),
                    )
                    if AUTO_MATRIX_EVAL_REFRESH:
                        report = refresh_matrix_eval_report()
                        yield await emit_log(
                            "LEARN",
                            (
                                f"MATRIX AUTO-UPDATE: {json.dumps(matrix_update, ensure_ascii=False)} | "
                                f"tool_accuracy={report.get('tool_accuracy', 0):.2f} "
                                f"path_resolution_success={report.get('path_resolution_success', 0):.2f} "
                                f"choice_constraint_success={report.get('choice_constraint_success', 0):.2f}"
                            ),
                            "UPDATED",
                        )
                    else:
                        yield await emit_log(
                            "LEARN",
                            f"MATRIX AUTO-UPDATE: {json.dumps(matrix_update, ensure_ascii=False)}",
                            "UPDATED",
                        )
                except Exception as e:
                    yield await emit_log("LEARN", f"MATRIX AUTO-UPDATE ERROR: {str(e)}", "ERROR")

            # --- OPTIMIZATION: SHORT-CIRCUIT ---
            # Nếu đã có dữ liệu và tool là search/get, kết thúc sớm để tiết kiệm LLM call (Evaluator)
            if state["observations"] and len(state["observations"]) > 0:
                if tool in ("list_accounts", "list_contacts", "list_contracts", "list_opportunities", "get_contract_details"):
                     yield await emit_log("EVAL", "FAST-TRACK: Đã tìm thấy dữ liệu. Bỏ qua bước kiểm tra chậm.", "SUCCESS")
                     state["is_finished"] = True
                     break

            # 4. EVALUATOR (Chỉ gọi khi thực sự cần thiết)
            yield await emit_log("EVAL", f"INPUT [Verify]: Kiểm tra tính đầy đủ...", "CHECKING")
            eval_result = evaluator_node(state)
            
            state["is_finished"] = eval_result.get("is_finished", False)
            for eval_log in eval_result.get("node_logs", []):
                yield await emit_log(eval_log.get("block"), f"OUTPUT: {eval_log.get('content')}", eval_log.get("status"))

        # FINAL RESULT
        yield await emit_log("TRACE", "END: Trả kết quả về giao diện.", "COMPLETE")
        final_payload = {
            "type": "final",
            "role": detected_role,
            "domain": domain,
            "session_id": current_session_id,
            "conversation_id": current_conversation_id,
            "context_key": context_key,
            "final_result": state["observations"],
            "planner_trace": state.get("planner_trace", {}),
            "selected_tool": state.get("selected_tool"),
            "selected_args": state.get("selected_args", {}),
            "db_call_executed": bool(state.get("db_call_executed")),
            "entity_match_result": {
                "ok": bool(state.get("entity_match_ok", True)),
                "reason": state.get("entity_match_reason", ""),
                "target_identities": state.get("planner_trace", {}).get("target_identities", []),
            },
        }
        if ENABLE_TRACE_TOKEN_STATS:
            final_payload["token_trace"] = stage_token_stats
            final_payload["planner_trace"]["token_trace"] = stage_token_stats
        if perception_trace:
            final_payload["planner_trace"]["perception_trace"] = perception_trace
        yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
