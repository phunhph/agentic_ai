"""
v2/contracts.py
Backwards compatibility shim — re-exports from core/contracts.py.
"""
from core.contracts import (
    FilterOp,
    RequestFilter,
    IngestResult,
    ExecutionPlan,
    ValidationResult,
    ExecutionResult,
    LessonOutcome,
)

__all__ = [
    "FilterOp",
    "RequestFilter",
    "IngestResult",
    "ExecutionPlan",
    "ValidationResult",
    "ExecutionResult",
    "LessonOutcome",
]
