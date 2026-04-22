from __future__ import annotations

import re
from typing import Iterable

from core.metadata_provider import get_metadata_provider
from tools.tool_registry import TOOL_REGISTRY

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+")


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_PATTERN.finditer(text or "")}


def infer_best_tool_for_tables(
    tables: Iterable[str],
    *,
    allowed_tools: set[str] | None = None,
    default_tool: str = "list_accounts",
) -> str:
    provider = get_metadata_provider()
    table_list = [t for t in tables if t]
    candidates = list(TOOL_REGISTRY.keys())
    if allowed_tools is not None:
        candidates = [t for t in candidates if t in allowed_tools]
    if not candidates:
        return default_tool

    best_tool = default_tool if default_tool in candidates else candidates[0]
    best_score = -1.0

    for tool in candidates:
        terms = _tokenize(f"{tool} {TOOL_REGISTRY.get(tool, {}).get('description', '')}")
        score = 0.0
        for table in table_list:
            aliases = provider.get_alias_terms_for_table(table)
            score += float(len(aliases.intersection(terms)))
        # Slight preference for list_* tools when table context exists.
        if table_list and tool.startswith("list_"):
            score += 0.5
        if score > best_score:
            best_score = score
            best_tool = tool
    return best_tool

