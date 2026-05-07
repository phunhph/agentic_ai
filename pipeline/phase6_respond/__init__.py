"""
phase6_respond/__init__.py
Package phase6_respond — response generation layer.
"""
from pipeline.phase6_respond.builder import (
    build_professional_response,
    build_clarify_suggestion,
    build_learning_summary,
)
from pipeline.phase6_respond.agentic import build_agentic_response
from pipeline.phase6_respond.tactician import apply_tactician_layer, apply_lean_personalization

__all__ = [
    "build_professional_response",
    "build_clarify_suggestion",
    "build_learning_summary",
    "build_agentic_response",
    "apply_tactician_layer",
    "apply_lean_personalization",
]
