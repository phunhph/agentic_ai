"""
phase6_respond/agentic.py
Tách từ v2/service.py — LLM-based agentic response generator.
"""
from __future__ import annotations

import json

from clients.llm import get_dynamic_client
from pipeline.phase6_respond.builder import build_professional_response


def build_agentic_response(
    query: str,
    rows: list[dict],
    execution_trace: dict,
    locale: str = "vi",
    role: str = "DEFAULT",
) -> str:
    """
    Dùng LLM để generate professional, contextualized response dựa trên dữ liệu.
    Fallback sang deterministic response nếu LLM thất bại.
    """
    client = get_dynamic_client("chat")

    try:
        data_summary = json.dumps(rows[:5], indent=2, ensure_ascii=False)

        prompt = f"""
You are a professional CRM assistant. Your task is to summarize the retrieved data for the user in a natural, helpful way.

USER QUERY: {query}
USER ROLE: {role}
LOCALE: {locale}
DATA RETRIEVED ({len(rows)} rows total):
{data_summary if rows else "NO DATA FOUND (0 rows)"}

RULES:
1. If there are many rows, provide a high-level summary.
2. If there is only 1 row, provide key details naturally.
3. Be professional and concise.
4. Respond in the requested LOCALE ({locale}).
5. Use markdown for better readability.
6. Do NOT mention technical details like table names (e.g., use 'Account' instead of 'hbl_account').
7. If NO DATA was found, explain politely and suggest what the user might do next (e.g., check name spelling or search broader).

RESPONSE:
"""
        response = client.generate(prompt, format="text")
        content = response.get("response", "").strip()
        if content:
            return content
    except Exception as e:
        print(f"Error creating agentic response: {str(e)}")

    # Fallback sang deterministic response nếu LLM fail
    return build_professional_response(query, rows, execution_trace, locale)


# Alias cho backwards compat
_build_agentic_response = build_agentic_response
