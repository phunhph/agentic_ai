"""
clients/llm.py
Move từ v2/api_clients.py — LLM & external API client factory.
Re-export từ v2/api_clients để duy trì single source of truth.
"""
# Re-export from v2/api_clients.py — single source of truth
from v2.api_clients import get_dynamic_client, APIClient

__all__ = ["get_dynamic_client", "APIClient"]
