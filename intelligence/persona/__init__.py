"""
intelligence/persona/__init__.py
Package intelligence/persona — role-based persona & tactician layer.
"""
from intelligence.persona.core import build_tactician_payload
from intelligence.persona.profile import build_persona_context

__all__ = ["build_tactician_payload", "build_persona_context"]
