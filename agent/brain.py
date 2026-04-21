import json
import ollama
from pathlib import Path

from infra.context import normalize_role
from infra.domain import normalize_domain_key
from memory.learning import AgentLearning
from memory.manager import AgentMemory
from infra.policy import ROLE_TOOL_ALLOWLIST
from infra.schemas import PlannerDecision
from infra.settings import OLLAMA_CHAT_MODEL
from memory.vector_store import MetadataRAG

rag = MetadataRAG()
learning = AgentLearning()
_episodic = AgentMemory()

_PROMPT_TEMPLATE: str | None = None
_PLANNING_CACHE: dict[str, dict] = {}


def _get_prompt_template() -> str:
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is None:
        # Note: adjust path if necessary. Original was .parent.parent / "config" / "brain_prompt.txt"
        # If this is now in agent/brain.py, parent is agent/, parent.parent is root.
        path = Path(__file__).resolve().parent.parent / "config" / "brain_prompt.txt"
        _PROMPT_TEMPLATE = path.read_text(encoding="utf-8")
    return _PROMPT_TEMPLATE


def agent_brain(state: dict):
    goal = state["goal"]
    role = normalize_role(state.get("role", "BUYER"))
    domain = normalize_domain_key(state.get("domain"))
    
    # 1. CHECK CACHE (Tối ưu tốc độ)
    cache_key = f"{role}:{domain}:{goal}"
    if state.get("iteration", 1) == 1 and cache_key in _PLANNING_CACHE:
        cached_res = _PLANNING_CACHE[cache_key]
        # Thêm trace để biết là từ cache
        cached_res["trace"]["cached"] = True
        return cached_res

    allowed_tools = sorted(ROLE_TOOL_ALLOWLIST.get(role, set()))

    relevant_schema = rag.get_relevant_schema(goal)
    past_experience = learning.recall_memory(goal, role, domain)
    episodic_advice = _episodic.get_advice(
        goal, context_key=state.get("context_key")
    )
    
    # ... (rest of the prompt logic remains same)
    previous_obs = state.get("observations", [])
    obs_context = (
        json.dumps(previous_obs, ensure_ascii=False) if previous_obs else "Chưa có dữ liệu."
    )

    history = state.get("history", [])
    history_context = (
        "\n".join(
            [f"User: {h['goal']}\nAssistant: {h['result']}" for h in history[-3:]]
        )
        if history
        else "Không có lịch sử hội thoại."
    )

    prompt = _get_prompt_template().format(
        relevant_schema=relevant_schema,
        past_experience=past_experience,
        episodic_advice=episodic_advice,
        history_context=history_context,
        obs_context=obs_context,
        role=role,
        domain=domain,
        goal=goal,
        iteration=state.get("iteration", 1),
        allowed_tools=allowed_tools,
    )

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = ollama.generate(
                model=OLLAMA_CHAT_MODEL, prompt=prompt, format="json"
            )
            raw = json.loads(response["response"])
            validated = PlannerDecision.model_validate(
                {
                    "thought": raw.get("thought", "..."),
                    "tool": raw.get("tool", "list_accounts"),
                    "args": raw.get("args") if isinstance(raw.get("args"), dict) else {},
                }
            )
            result = validated.model_dump()
            result["trace"] = {
                "relevant_schema": relevant_schema,
                "past_experience": past_experience,
                "episodic_advice": episodic_advice,
                "history_turns_used": len(history[-3:]),
                "previous_observations_count": len(previous_obs),
                "iteration": state.get("iteration", 1),
                "role": role,
                "domain": domain,
                "cached": False
            }
            
            # SAVE TO CACHE (chỉ save ở iteration 1 để tránh loop cache)
            if state.get("iteration", 1) == 1:
                _PLANNING_CACHE[cache_key] = result
                
            return result
        except Exception:
            if attempt < max_retries:
                continue
            return {
                "thought": "Lỗi xử lý. Thử tìm kiếm.",
                "tool": "list_accounts",
                "args": {},
                "trace": {
                    "relevant_schema": relevant_schema,
                    "past_experience": past_experience,
                    "episodic_advice": episodic_advice,
                    "history_turns_used": len(history[-3:]),
                    "previous_observations_count": len(previous_obs),
                    "iteration": state.get("iteration", 1),
                    "role": role,
                    "domain": domain,
                    "error": "LLM reasoning failed after retries",
                    "cached": False
                },
            }
