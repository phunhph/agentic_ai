from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


FilterOp = Literal["eq", "contains", "in", "range"]


@dataclass
class RequestFilter:
    field: str
    op: FilterOp
    value: Any


@dataclass
class IngestResult:
    raw_query: str
    normalized_query: str
    intent: str
    entities: list[str]
    request_filters: list[RequestFilter] = field(default_factory=list)
    update_data: dict[str, Any] = field(default_factory=dict)
    ambiguity_score: float = 0.0
    role: str = "DEFAULT"
    domain: str = "general"
    persona_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    root_table: str
    join_path: list[dict[str, Any]] = field(default_factory=list)
    where_filters: list[RequestFilter] = field(default_factory=list)
    update_data: dict[str, Any] = field(default_factory=dict)
    aggregate_ops: list[dict[str, Any]] = field(default_factory=list)
    limit: int = 0
    include_tables: list[str] = field(default_factory=list)
    keyword: str = ""
    tactical_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    data: list[dict[str, Any]]
    execution_trace: dict[str, Any]
    success: bool

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, index):
        return self.data[index]

    def __bool__(self):
        return bool(self.data)


@dataclass
class LessonOutcome:
    query: str
    execution_plan: ExecutionPlan
    success: bool
    score_breakdown: dict[str, float]
    diagnostics: dict[str, Any] = field(default_factory=dict)
