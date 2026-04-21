from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RequestFilter(BaseModel):
    field: str
    op: Literal["eq", "contains"] = "contains"
    value: Any


class NormalizedRequest(BaseModel):
    intent: str = "UNKNOWN"
    tool_hint: str = ""
    entities: dict[str, Any] = Field(default_factory=dict)
    filters: list[RequestFilter] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    valid: bool = True
    reason: str = ""
