"""Schema chuẩn cho agent context và payload trace (Pydantic v2)."""

from typing import Any

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Ngữ cảnh một lần chạy agent (tương thích dict state hiện tại)."""

    goal: str
    role: str = "BUYER"
    session_id: str = ""
    conversation_id: str = ""
    context_key: str = ""
    domain: str = "general"
    history: list[dict[str, Any]] = Field(default_factory=list)
    is_finished: bool = False
    iteration: int = 0
    steps: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class TraceLogPayload(BaseModel):
    """Một dòng log SSE (block + metadata)."""

    block: str
    content: str
    status: str = "INFO"
    role: str = "BUYER"
    session_id: str = ""
    conversation_id: str = ""
    context_key: str = ""

    model_config = {"extra": "allow"}


class PlannerDecision(BaseModel):
    """Output JSON mong đợi từ planner / LLM."""

    thought: str = "..."
    tool: str = "list_accounts"
    args: dict[str, Any] = Field(default_factory=dict)
