"""
DANN - LangGraph Multi-Agent Orchestrator
Nodes: Router → Gatekeeper → [Analyst | Operator | Tactician | Compass]
Reasoning: Chain-of-Thought + Tree-of-Thoughts
"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any, Optional, TypedDict
import os

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from card_engine.builder import CardViewEngine


# ─── State ────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    sender_id: str
    space_id: str
    raw_text: str
    # Router output
    intent: Optional[str]          # QUERY | UPDATE | CREATE | HELP | COMPASS
    confidence: Optional[float]
    extracted_entities: Optional[dict]
    # Gatekeeper output
    needs_clarification: bool
    clarification_options: Optional[list[dict]]
    clarification_question: Optional[str]
    # Resolution
    matched_account: Optional[dict]
    matched_opportunity: Optional[dict]
    sender_profile: Optional[dict]
    # Reasoning trace (CoT)
    reasoning_trace: Optional[str]
    # Final output
    card_response: Optional[dict]
    plain_response: Optional[str]
    error: Optional[str]


# ─── LLM Setup ────────────────────────────────────────────────────────────────

def get_llm(temperature: float = 0.1) -> ChatOllama:
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3:8b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=temperature,
        num_predict=2000,
    )


# ─── Node: Router ─────────────────────────────────────────────────────────────

ROUTER_SYSTEM = """Bạn là Router Node của hệ thống CRM AI. Phân tích tin nhắn và trả về JSON.

Intent types:
- UPDATE: Cập nhật thông tin deal/khách hàng (budget, stage, contact, BANT)
- QUERY: Truy vấn dữ liệu, báo cáo, pipeline
- CREATE: Tạo mới account/opportunity/contact
- HELP: Hỏi về cách dùng hệ thống
- COMPASS: Xin lời khuyên tactical, daily briefing

Chain-of-Thought reasoning:
1. Đọc tin nhắn → xác định động từ hành động chính
2. Tìm entity được đề cập (account name, deal, số tiền, stage)
3. Xác định intent dựa trên pattern
4. Tính confidence dựa trên độ rõ ràng

Trả về JSON duy nhất (không có markdown):
{
  "intent": "UPDATE|QUERY|CREATE|HELP|COMPASS",
  "confidence": 0.0-1.0,
  "reasoning": "CoT trace ngắn gọn",
  "entities": {
    "account_name": "tên công ty nếu có",
    "opportunity_name": "tên deal nếu có",
    "budget": "số tiền budget nếu có, kèm đơn vị",
    "authority": "tên/chức vụ người quyết định nếu có",
    "need": "nhu cầu/vấn đề nếu có",
    "timeline": "thời hạn nếu có",
    "stage": "giai đoạn pipeline nếu có",
    "contact_name": "tên người liên hệ nếu có"
  }
}"""


async def router_node(state: AgentState) -> AgentState:
    """Intent classification with Chain-of-Thought reasoning"""
    llm = get_llm(temperature=0.0)

    # Build context from conversation history
    history_context = ""
    if state.get("messages"):
        recent = state["messages"][-3:]  # Last 3 turns
        history_context = "\nLịch sử gần đây:\n" + "\n".join(
            f"[{m.type}]: {m.content[:100]}" for m in recent
        )

    prompt = f"Tin nhắn: {state['raw_text']}{history_context}"

    response = await llm.ainvoke([
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        raw = response.content
        # Strip markdown if any
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        return {
            **state,
            "intent": data.get("intent", "HELP"),
            "confidence": float(data.get("confidence", 0.5)),
            "extracted_entities": data.get("entities", {}),
            "reasoning_trace": data.get("reasoning", ""),
        }
    except Exception as e:
        return {
            **state,
            "intent": "HELP",
            "confidence": 0.3,
            "extracted_entities": {},
            "error": f"Router parse error: {e}",
        }


# ─── Node: Gatekeeper ─────────────────────────────────────────────────────────

GATEKEEPER_SYSTEM = """Bạn là Gatekeeper Node. Kiểm tra xem thông tin có đủ để thực hiện action không.

Nếu confidence < 0.85 HOẶC thiếu thông tin quan trọng:
- needs_clarification: true
- Tạo câu hỏi rõ ràng + 2-4 lựa chọn button

Nếu đủ thông tin:
- needs_clarification: false

Trả về JSON:
{
  "needs_clarification": true/false,
  "question": "Câu hỏi nếu cần làm rõ",
  "options": [
    {"label": "Lựa chọn 1", "action_id": "resolve_option_1", "payload": {}},
    {"label": "Lựa chọn 2", "action_id": "resolve_option_2", "payload": {}}
  ],
  "reasoning": "Lý do cần clarification"
}"""


async def gatekeeper_node(state: AgentState) -> AgentState:
    """Confidence check + ambiguity detection"""
    confidence = state.get("confidence", 0.5)
    entities = state.get("extracted_entities", {})
    intent = state.get("intent", "HELP")

    # Fast path: obvious intents with high confidence
    if confidence >= 0.85 and entities.get("account_name"):
        return {**state, "needs_clarification": False}

    # COMPASS/HELP don't need entity resolution
    if intent in ("COMPASS", "HELP"):
        return {**state, "needs_clarification": False}

    llm = get_llm(temperature=0.0)
    prompt = f"""
Intent: {intent}
Confidence: {confidence}
Entities extracted: {json.dumps(entities, ensure_ascii=False)}
Raw message: {state['raw_text']}

Cần clarification không?"""

    response = await llm.ainvoke([
        SystemMessage(content=GATEKEEPER_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        raw = re.sub(r"```json|```", "", response.content).strip()
        data = json.loads(raw)
        if data.get("needs_clarification"):
            return {
                **state,
                "needs_clarification": True,
                "clarification_question": data.get("question", "Bạn muốn cập nhật gì?"),
                "clarification_options": data.get("options", []),
            }
        return {**state, "needs_clarification": False}
    except Exception:
        return {**state, "needs_clarification": False}


# ─── Node: Analyst ────────────────────────────────────────────────────────────

ANALYST_SYSTEM = """Bạn là Analyst Node - chuyên gia truy vấn CRM và phân tích deal.

Phân tích câu hỏi và tạo phản hồi dạng key-value cho Card V2.
Sử dụng Tree-of-Thoughts: Xem xét nhiều góc độ phân tích khác nhau trước khi trả lời.

Trả về JSON:
{
  "title": "Tiêu đề báo cáo",
  "summary": "1 câu tóm tắt",
  "rows": [{"Trường": "Giá trị"}, ...],
  "tactical_insight": "Insight tactical dựa trên data (nếu có)"
}"""


async def analyst_node(state: AgentState) -> AgentState:
    """Query and analysis with Tree-of-Thoughts reasoning"""
    llm = get_llm(temperature=0.2)
    profile = state.get("sender_profile", {})
    experience = profile.get("experience_level", "junior") if profile else "junior"

    # Adapt response depth based on experience level (DC5)
    adaptation = (
        "Trả lời ngắn gọn, rõ ràng. Đưa ra 1-3 lựa chọn cụ thể." if experience == "junior"
        else "Phân tích sâu, chiến lược. Đặt câu hỏi mở để khai thác thêm."
    )

    prompt = f"""
Query: {state['raw_text']}
Account context: {json.dumps(state.get('matched_account', {}), ensure_ascii=False, default=str)}
Opportunity context: {json.dumps(state.get('matched_opportunity', {}), ensure_ascii=False, default=str)}
Experience level: {experience} → {adaptation}

Phân tích và trả về JSON."""

    response = await llm.ainvoke([
        SystemMessage(content=ANALYST_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        raw = re.sub(r"```json|```", "", response.content).strip()
        data = json.loads(raw)
        card = CardViewEngine.build_query_result_card(
            title=data.get("title", "Kết quả phân tích"),
            rows=data.get("rows", []),
            confidence=state.get("confidence", 0.8),
            summary=data.get("summary"),
        )
        return {**state, "card_response": card}
    except Exception as e:
        return {**state, "error": f"Analyst error: {e}"}


# ─── Node: Operator ───────────────────────────────────────────────────────────

OPERATOR_SYSTEM = """Bạn là Operator Node - ghi CRM từ tin nhắn tự nhiên.

Trích xuất và cấu trúc hóa dữ liệu để cập nhật vào DB.
Dùng Chain-of-Thought: Extract → Validate → Transform → Confirm

Trả về JSON:
{
  "action": "update_bant|update_stage|create_opportunity|update_contact",
  "account_name": "...",
  "changes": {
    "budget": "$50,000 hoặc null",
    "authority": "VP of Sales hoặc null",
    "need": "mô tả nhu cầu hoặc null",
    "timeline": "Q3 2026 hoặc null",
    "stage": "tên stage mới hoặc null"
  },
  "changed_fields": ["budget", "authority"],
  "prev_stage": "Discovery (nếu là stage change)",
  "new_stage": "Negotiation (nếu là stage change)",
  "mixs_extras": {"key": "value thêm nào không fit BANT"},
  "confidence": 0.0-1.0,
  "summary": "Tóm tắt hành động vừa thực hiện"
}"""


async def operator_node(state: AgentState) -> AgentState:
    """Extract and structure CRM data updates"""
    llm = get_llm(temperature=0.0)
    entities = state.get("extracted_entities", {})
    account = state.get("matched_account", {})

    prompt = f"""
Tin nhắn: {state['raw_text']}
Pre-extracted entities: {json.dumps(entities, ensure_ascii=False)}
Account hiện tại: {json.dumps(account, ensure_ascii=False, default=str)}
Opportunity hiện tại: {json.dumps(state.get('matched_opportunity', {}), ensure_ascii=False, default=str)}

Trích xuất và cấu trúc hóa để cập nhật CRM."""

    response = await llm.ainvoke([
        SystemMessage(content=OPERATOR_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        raw = re.sub(r"```json|```", "", response.content).strip()
        data = json.loads(raw)
        changes = data.get("changes", {})
        action = data.get("action", "update_bant")

        if action == "update_stage":
            card = CardViewEngine.build_pipeline_move_card(
                account_name=account.get("hbl_account_name", "Unknown"),
                prev_stage=data.get("prev_stage", "—"),
                new_stage=data.get("new_stage", "—"),
                actor=state["sender_id"],
                confidence=data.get("confidence", state.get("confidence", 0.9)),
                message_id=state.get("space_id"),
            )
        else:
            profile = state.get("sender_profile", {})
            card = CardViewEngine.build_success_update_card(
                account_name=account.get("hbl_account_name", entities.get("account_name", "Account")),
                opportunity_name=entities.get("opportunity_name"),
                budget=changes.get("budget"),
                authority=changes.get("authority"),
                need=changes.get("need"),
                timeline=changes.get("timeline"),
                changed_fields=data.get("changed_fields", []),
                confidence=data.get("confidence", state.get("confidence", 0.9)),
                message_id=state.get("space_id"),
            )

        return {
            **state,
            "card_response": card,
            "plain_response": data.get("summary", "Đã cập nhật CRM."),
        }
    except Exception as e:
        return {**state, "error": f"Operator error: {e}"}


# ─── Node: Tactician ──────────────────────────────────────────────────────────

TACTICIAN_SYSTEM = """Bạn là Extraction Tactician Node.
Phát hiện deal stall và đề xuất hành động cụ thể.

Tree-of-Thoughts approach:
Branch A: Thiếu Economic Buyer → Approach strategy
Branch B: Thiếu Timeline → Urgency creation tactics
Branch C: Budget freeze → ROI justification
Branch D: Technical blockers → SE involvement

Chọn branch phù hợp nhất và trả về JSON:
{
  "stall_detected": true/false,
  "stall_reason": "Lý do deal chững",
  "branch_chosen": "A|B|C|D",
  "proposed_action": "Hành động cụ thể",
  "email_template": "Template email nếu applicable",
  "confidence": 0.0-1.0
}"""


async def tactician_node(state: AgentState) -> AgentState:
    """Deal stall detection and intervention - Phase 4"""
    llm = get_llm(temperature=0.3)
    opp = state.get("matched_opportunity", {})
    profile = state.get("sender_profile", {})
    experience = profile.get("experience_level", "junior") if profile else "junior"

    prompt = f"""
Tin nhắn: {state['raw_text']}
Opportunity data: {json.dumps(opp, ensure_ascii=False, default=str)}
Sender experience: {experience}
Missing BANT: check budget/authority/need/timeline từ opportunity data

Phân tích và đề xuất action."""

    response = await llm.ainvoke([
        SystemMessage(content=TACTICIAN_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        raw = re.sub(r"```json|```", "", response.content).strip()
        data = json.loads(raw)
        account = state.get("matched_account", {})
        card = CardViewEngine.build_extraction_tactician_card(
            account_name=account.get("hbl_account_name", "Deal"),
            stall_reason=data.get("stall_reason", "Thiếu thông tin"),
            proposed_action=data.get("proposed_action", ""),
            email_template=data.get("email_template"),
            confidence=data.get("confidence", 0.75),
        )
        return {**state, "card_response": card}
    except Exception as e:
        return {**state, "error": f"Tactician error: {e}"}


# ─── Node: Compass ────────────────────────────────────────────────────────────

COMPASS_SYSTEM = """Bạn là Daily Compass Node - trợ lý tactical cá nhân.

Thích nghi theo experience level:
- Junior: Đưa ra 3 hành động cụ thể, đóng/rõ ràng, ưu tiên cao nhất trước
- Senior: Phân tích chiến lược, đặt câu hỏi gợi mở, kết nối deal với big picture

Trả về JSON:
{
  "briefing": "Tóm tắt tình hình hiện tại (2-3 câu)",
  "action_items": ["Hành động 1", "Hành động 2", "Hành động 3"],
  "confidence": 0.0-1.0
}"""


async def compass_node(state: AgentState) -> AgentState:
    """Personalized tactical compass - adapts by experience level"""
    llm = get_llm(temperature=0.4)
    profile = state.get("sender_profile", {})
    experience = (profile.get("experience_level", "junior") if profile else "junior")
    name = (profile.get("display_name", "bạn") if profile else "bạn")

    prompt = f"""
Request: {state['raw_text']}
Sender: {name}, Level: {experience}
Accounts context: {json.dumps(state.get('matched_account', {}), ensure_ascii=False, default=str)[:500]}

Tạo briefing tactical phù hợp."""

    response = await llm.ainvoke([
        SystemMessage(content=COMPASS_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        raw = re.sub(r"```json|```", "", response.content).strip()
        data = json.loads(raw)
        card = CardViewEngine.build_compass_card(
            sender_name=name,
            experience_level=experience,
            briefing=data.get("briefing", ""),
            action_items=data.get("action_items", []),
            confidence=data.get("confidence", 0.8),
        )
        return {**state, "card_response": card}
    except Exception as e:
        return {**state, "error": f"Compass error: {e}"}


# ─── Node: Fallback (Gatekeeper Resolver) ─────────────────────────────────────

async def fallback_node(state: AgentState) -> AgentState:
    """Build fallback card when clarification needed"""
    card = CardViewEngine.build_fallback_card(
        question=state.get("clarification_question", "Bạn muốn làm gì?"),
        options=state.get("clarification_options", []),
        confidence=state.get("confidence", 0.5),
    )
    return {**state, "card_response": card}


# ─── Node: Error Handler ──────────────────────────────────────────────────────

async def error_node(state: AgentState) -> AgentState:
    """Build error card"""
    entities = state.get("extracted_entities", {})
    entity_name = entities.get("account_name") or entities.get("opportunity_name") or "thực thể"
    card = CardViewEngine.build_error_card(
        entity=entity_name,
        message=state.get("error", "Lỗi không xác định. Vui lòng thử lại."),
        fallback_action_label="Tạo mới" if state.get("intent") == "CREATE" else None,
    )
    return {**state, "card_response": card}


# ─── Routing logic ─────────────────────────────────────────────────────────────

def route_after_gatekeeper(state: AgentState) -> str:
    if state.get("needs_clarification"):
        return "fallback"
    intent = state.get("intent", "HELP")
    return {
        "QUERY": "analyst",
        "UPDATE": "operator",
        "CREATE": "operator",
        "COMPASS": "compass",
        "HELP": "compass",
    }.get(intent, "compass")


def route_after_operator(state: AgentState) -> str:
    if state.get("error"):
        return "error_handler"
    return END


def route_after_analyst(state: AgentState) -> str:
    if state.get("error"):
        return "error_handler"
    # Check if tactician should also run
    opp = state.get("matched_opportunity")
    if opp and not state.get("card_response"):
        return "tactician"
    return END


# ─── Graph Assembly ────────────────────────────────────────────────────────────

def build_dann_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("gatekeeper", gatekeeper_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("operator", operator_node)
    graph.add_node("tactician", tactician_node)
    graph.add_node("compass", compass_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("error_handler", error_node)

    graph.set_entry_point("router")
    graph.add_edge("router", "gatekeeper")

    graph.add_conditional_edges(
        "gatekeeper",
        route_after_gatekeeper,
        {
            "fallback": "fallback",
            "analyst": "analyst",
            "operator": "operator",
            "compass": "compass",
        },
    )

    graph.add_conditional_edges(
        "operator",
        route_after_operator,
        {"error_handler": "error_handler", END: END},
    )

    graph.add_conditional_edges(
        "analyst",
        route_after_analyst,
        {"error_handler": "error_handler", "tactician": "tactician", END: END},
    )

    graph.add_edge("tactician", END)
    graph.add_edge("compass", END)
    graph.add_edge("fallback", END)
    graph.add_edge("error_handler", END)

    return graph.compile()


# Singleton compiled graph
dann_graph = build_dann_graph()