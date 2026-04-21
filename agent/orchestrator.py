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
        perception_result = perception_node({"goal": goal, "role": session_role})
        clean_goal = perception_result["goal"]
        detected_role = perception_result.get("role", role)
        domain = normalize_domain_key(infer_domain(clean_goal))

        yield await emit_log(
            "TRACE",
            "Bắt đầu luồng Agent (PERCEIVE -> REASON -> ACT -> EVAL -> LEARN -> FINAL)",
            "START",
        )
        await asyncio.sleep(0.1)
        yield await emit_log(
            "PERCEIVE",
            f'Input chuẩn hóa: "{clean_goal}" | Role: {detected_role} | Domain: {domain}',
            "DONE",
        )
        await asyncio.sleep(0.1)

        # STATE
        state = {
            "goal": clean_goal,
            "role": detected_role,
            "domain": domain,
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
            yield await emit_log(
                "TRACE", f"Bắt đầu iteration {state['iteration']}/5", "ITERATING"
            )
            await asyncio.sleep(0.1)

            # 2. PLANNING
            decision = agent_brain(state)
            thought = decision.get("thought", "...")
            tool = decision.get("tool", "error")
            args = decision.get("args", {})
            trace = decision.get("trace", {})

            yield await emit_log("REASON", thought, "THINKING")
            await asyncio.sleep(0.1)
            yield await emit_log(
                "REASON",
                f"Chọn tool='{tool}' args={json.dumps(args, ensure_ascii=False)} | obs_prev={trace.get('previous_observations_count', 0)}",
                "DECIDED",
            )
            await asyncio.sleep(0.1)
            yield await emit_log(
                "REASON",
                f"Schema context: {trace.get('relevant_schema', 'N/A')}",
                "CONTEXT",
            )
            await asyncio.sleep(0.1)
            yield await emit_log(
                "LEARN",
                f"Bài học vector: {trace.get('past_experience', 'N/A')} | Episodic: {trace.get('episodic_advice', 'N/A')}",
                "CONTEXT",
            )
            await asyncio.sleep(0.1)

            if tool not in ("final_answer", "error"):
                allowed, deny_reason = is_tool_allowed(detected_role, tool)
                if not allowed:
                    yield await emit_log("POLICY", deny_reason, "DENIED")
                    await asyncio.sleep(0.1)
                    state["observations"] = []
                    eval_result = evaluator_node(state)
                    state["is_finished"] = eval_result.get("is_finished", False)
                    for eval_log in eval_result.get("node_logs", []):
                        yield await emit_log(
                            eval_log.get("block", "EVAL"),
                            eval_log.get("content", ""),
                            eval_log.get("status", "INFO"),
                        )
                        await asyncio.sleep(0.1)
                    continue

            if tool == "final_answer":
                state["is_finished"] = True
                self.memory.save_experience(
                    clean_goal,
                    "completed",
                    len(state["observations"]),
                    context_key=context_key,
                )
                yield await emit_log(
                    "LEARN", "Đã lưu final experience vào memory.", "RECORDED"
                )
                await asyncio.sleep(0.1)
                yield await emit_log("EVAL", "Hoàn tất mục tiêu.", "DONE")
                await asyncio.sleep(0.1)
                break

            if tool == "error":
                state["is_finished"] = True
                yield await emit_log(
                    "EVAL", "Không chọn được tool hợp lệ. Dừng vòng lặp.", "FAILED"
                )
                await asyncio.sleep(0.1)
                break

            # 3. EXECUTION
            state["next_action"] = tool
            state["next_args"] = args
            act_res = action_node(state)
            state["observations"] = act_res["observations"]

            for log_item in act_res.get("node_logs", []):
                yield await emit_log(
                    log_item.get("block", "ACT"),
                    log_item.get("content", ""),
                    log_item.get("status", "INFO"),
                )
                await asyncio.sleep(0.1)
            yield await emit_log(
                "TRACE",
                f"Observation count hiện tại: {len(state['observations'])}",
                "OBSERVED",
            )
            await asyncio.sleep(0.1)

            # 4. EVALUATOR
            eval_result = evaluator_node(state)
            state["is_finished"] = eval_result.get("is_finished", False)
            for eval_log in eval_result.get("node_logs", []):
                yield await emit_log(
                    eval_log.get("block", "EVAL"),
                    eval_log.get("content", ""),
                    eval_log.get("status", "INFO"),
                )
                await asyncio.sleep(0.1)
            if state["is_finished"]:
                obs_count = len(state["observations"])
                yield await emit_log("EVAL", f"Kết quả cuối: {obs_count} bản ghi.", "DONE")
                await asyncio.sleep(0.1)

        # FINAL RESULT
        yield await emit_log(
            "TRACE", "Kết thúc luồng Agent, trả final_result về UI.", "END"
        )
        await asyncio.sleep(0.1)
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
