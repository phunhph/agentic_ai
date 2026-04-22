from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LearnedIdentity:
    type: str
    id: str | None = None
    name: str | None = None
    field: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name,
            "field": self.field,
            "confidence": float(self.confidence),
        }


@dataclass
class LearnedCase:
    query: str
    expected_tool: str
    expected_entities: list[str] = field(default_factory=list)
    target_identities: list[dict[str, Any]] = field(default_factory=list)
    usage_count: int = 0
    success_count: int = 0
    last_success: bool = False
    planner_mode: str = ""

    @property
    def success_ratio(self) -> float:
        if self.usage_count <= 0:
            return 0.0
        return self.success_count / self.usage_count

    def to_dict(self) -> dict[str, Any]:
        out = {
            "query": self.query,
            "expected_tool": self.expected_tool,
            "usage_count": int(self.usage_count),
            "success_count": int(self.success_count),
            "last_success": bool(self.last_success),
        }
        if self.expected_entities:
            out["expected_entities"] = self.expected_entities
        if self.target_identities:
            out["target_identities"] = self.target_identities
        if self.planner_mode:
            out["planner_mode"] = self.planner_mode
        return out

