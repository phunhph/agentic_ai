import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from agent.brain import agent_brain
from agent.dynamic_planner import plan_with_metadata
from agent.perception import perception_node
from agent.action import action_node
from agent.evaluator import evaluator_node
from memory.manager import AgentMemory
from infra.context import normalize_role, ensure_context_id, build_context_key
from infra.domain import infer_domain, normalize_domain_key
from infra.policy import is_tool_allowed
from infra.settings import ENABLE_DYNAMIC_METADATA_PLANNER
from infra.settings import (
    ENABLE_MATRIX_GATE,
    MATRIX_MIN_CHOICE_SUCCESS,
    MATRIX_MIN_PATH_SUCCESS,
    MATRIX_MIN_TOOL_ACCURACY,
)
from storage.database import SessionLocal
from storage.repositories.knowledge_repository import (
    find_similar_lessons,
    mark_lessons_outcome,
    record_correction,
)


class AgentOrchestrator:
    def __init__(self):
        self.memory = AgentMemory()

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
                user_role=str(feedback.get("role", "BUYER")).strip() or "BUYER",
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
        role: str = "BUYER",
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

        def evaluate_matrix_gate() -> tuple[bool, dict]:
            if not ENABLE_MATRIX_GATE:
                return True, {"enabled": False, "reason": "matrix gate disabled"}
            report_path = Path(__file__).resolve().parent.parent / "storage" / "dynamic_eval_report.json"
            if not report_path.exists():
                return False, {"enabled": True, "reason": "dynamic_eval_report.json missing"}
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                return False, {"enabled": True, "reason": "dynamic_eval_report.json unreadable"}
            tool_acc = float(report.get("tool_accuracy", 0.0))
            path_ok = float(report.get("path_resolution_success", 0.0))
            choice_ok = float(report.get("choice_constraint_success", 0.0))
            passed = (
                tool_acc >= MATRIX_MIN_TOOL_ACCURACY
                and path_ok >= MATRIX_MIN_PATH_SUCCESS
                and choice_ok >= MATRIX_MIN_CHOICE_SUCCESS
            )
            return passed, {
                "enabled": True,
                "tool_accuracy": tool_acc,
                "path_resolution_success": path_ok,
                "choice_constraint_success": choice_ok,
                "thresholds": {
                    "tool_accuracy": MATRIX_MIN_TOOL_ACCURACY,
                    "path_resolution_success": MATRIX_MIN_PATH_SUCCESS,
                    "choice_constraint_success": MATRIX_MIN_CHOICE_SUCCESS,
                },
            }

        # Parse history
        try:
            chat_history = json.loads(history)
        except Exception:
            chat_history = []
        matrix_gate_passed, matrix_gate_info = evaluate_matrix_gate()

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

        # 1. PERCEPTION
        yield await emit_log("TRACE", f"INPUT [Goal]: {goal}", "RECEIVING")
        perception_result = perception_node({"goal": goal, "role": session_role})
        
        clean_goal = perception_result["goal"]
        planner_goal = perception_result.get("planner_goal", clean_goal)
        detected_role = perception_result.get("role", role)
        intent = perception_result.get("intent", "UNKNOWN")
        entities = perception_result.get("entities", {})
        request_contract = perception_result.get("request_contract", {})
        domain = normalize_domain_key(infer_domain(clean_goal))
        maybe_record_correction(clean_goal, detected_role, domain)

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
        await asyncio.sleep(0.1)

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
        }

        while not state["is_finished"] and state["iteration"] < 5:
            state["iteration"] += 1
            yield await emit_log("TRACE", f"--- ITERATION {state['iteration']} ---", "START")

            # 2. PLANNING (BRAIN)
            yield await emit_log("REASON", f"INPUT [Context]: Goal + Memory + RAG", "PROCESSING")
            if ENABLE_DYNAMIC_METADATA_PLANNER and matrix_gate_passed:
                db = SessionLocal()
                try:
                    lessons = find_similar_lessons(
                        db,
                        query=state.get("goal", ""),
                        role=detected_role,
                        domain=domain,
                        limit=3,
                    )
                finally:
                    db.close()
                decision = plan_with_metadata(state, knowledge_hits=lessons)
                state["knowledge_hit_ids"] = [str(x.get("id")) for x in lessons if x.get("id")]
                decision.setdefault("trace", {})
                decision["trace"]["matrix_gate"] = matrix_gate_info
                if decision.get("tool") not in ("list_accounts", "list_contracts", "get_contract_details", "get_account_overview", "final_answer"):
                    decision = agent_brain(state)
                    decision.setdefault("trace", {})
                    decision["trace"]["fallback_reason"] = "dynamic planner tool mismatch; fallback legacy"
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
            state["planner_trace"] = trace

            yield await emit_log(
                "REASON", 
                f"OUTPUT [Decision]: Thought='{thought}' | Tool='{tool}' | Args={json.dumps(args, ensure_ascii=False)}", 
                "DECIDED"
            )
            await asyncio.sleep(0.1)
            
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
            act_res = action_node(state)
            
            state["observations"] = act_res["observations"]
            
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

            # --- OPTIMIZATION: SHORT-CIRCUIT ---
            # Nếu đã có dữ liệu và tool là search/get, kết thúc sớm để tiết kiệm LLM call (Evaluator)
            if state["observations"] and len(state["observations"]) > 0:
                if tool in ("list_accounts", "list_contracts", "get_contract_details"):
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
        }
        yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
