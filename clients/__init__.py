"""
clients/__init__.py
Package clients — LLM & external API clients.
"""
from clients.llm import get_dynamic_client, APIClient

__all__ = ["get_dynamic_client", "APIClient"]
