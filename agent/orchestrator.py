import json
import asyncio
from typing import AsyncGenerator
from agent.brain import agent_brain
from agent.perception import perception_node
from agent.action import action_node
from agent.evaluator import evaluator_node
from memory.manager import AgentMemory
from infra.context import normalize_role, ensure_context_id, build_context_key
from infra.domain import infer_domain, normalize_domain_key
from infra.policy import is_tool_allowed


class AgentOrchestrator:
    def __init__(self):
        self.memory = AgentMemory()

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

        # Parse history
        try:
            chat_history = json.loads(history)
        except Exception:
            chat_history = []

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
            decision = agent_brain(state)
            
            thought = decision.get("thought", "...")
            tool = decision.get("tool", "error")
            args = decision.get("args", {})
            trace = decision.get("trace", {})

            yield await emit_log(
                "REASON", 
                f"OUTPUT [Decision]: Thought='{thought}' | Tool='{tool}' | Args={json.dumps(args, ensure_ascii=False)}", 
                "DECIDED"
            )
            await asyncio.sleep(0.1)
            
            yield await emit_log(
                "LEARN",
                f"TRACE [Knowledge]: Recall='{trace.get('past_experience', 'N/A')}'",
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

            # --- OPTIMIZATION: SHORT-CIRCUIT ---
            # Nếu đã có dữ liệu và tool là search/get, kết thúc sớm để tiết kiệm LLM call (Evaluator)
            if state["observations"] and len(state["observations"]) > 0:
                if tool in ("search_products", "get_orders", "get_order_details"):
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
        }
        yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
