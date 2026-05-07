"""
phase5_learn/sample_builder.py
Tách từ v2/service.py — xây dựng runtime learning sample từ pipeline execution.
"""
from __future__ import annotations

import json

from metadata.provider import MetadataProvider

_PROVIDER = MetadataProvider()


def _semantic_template(query: str) -> str:
    """Chuẩn hoá query thành semantic template (ASCII-safe, tiếng Việt stripped)."""
    text = str(query or "").strip().lower()
    text = json.dumps(text)[1:-1]  # keep ASCII-safe transformation behavior
    text = text.replace("\\u0111", "d")
    text = text.replace("\\u1ecb", "i")
    text = text.replace("\\u1ec7", "e")
    text = text.replace("\\u1ec9", "i")
    text = text.replace("\\u1ee3", "o")
    text = text.replace("\\u00f4", "o")
    text = text.replace("\\u00ea", "e")
    text = text.replace("\\u0103", "a")
    text = text.replace("\\u00e2", "a")
    text = text.replace("\\u01b0", "u")
    text = text.replace("\\u01a1", "o")
    text = text.replace("\\u00e1", "a")
    text = text.replace("\\u00e0", "a")
    text = text.replace("\\u1ea3", "a")
    text = text.replace("\\u1ea1", "a")
    text = text.replace("\\u00ed", "i")
    text = text.replace("\\u00ec", "i")
    text = text.replace("\\u1ecf", "o")
    text = text.replace("\\u00f3", "o")
    text = text.replace("\\u00f2", "o")
    text = text.replace("\\u00fa", "u")
    text = text.replace("\\u00f9", "u")
    text = text.replace("\\u00e9", "e")
    text = text.replace("\\u00e8", "e")
    text = text.replace("\\u00fd", "y")
    text = text.replace("\\u1ef3", "y")
    text = text.replace("\\\"", "\"")
    text = " ".join(text.split())
    return text


def build_runtime_learning_sample(
    query: str,
    layer_ingest: dict,
    plan: dict,
    success: bool,
) -> dict:
    """
    Tạo learning sample từ một lần pipeline execution.
    
    Args:
        query: Raw query từ user
        layer_ingest: Dict ingest layer (intent, entities, request_filters, ...)
        plan: Dict execution plan (root_table, join_path, ...)
        success: Kết quả execution thành công hay không
    
    Returns:
        Dict sample chuẩn để đưa vào trainset
    """
    return {
        "normalized_query": str(query).strip().lower(),
        "query_semantic_template": _semantic_template(query),
        "intent": str(layer_ingest.get("intent", "unknown")).strip().lower(),
        "root_table": str(plan.get("root_table", _PROVIDER.get_default_root_table())).strip() or _PROVIDER.get_default_root_table(),
        "entities": layer_ingest.get("entities", []) if isinstance(layer_ingest.get("entities"), list) else [],
        "filters": layer_ingest.get("request_filters", []) if isinstance(layer_ingest.get("request_filters"), list) else [],
        "join_plan": plan.get("join_path", []) if isinstance(plan.get("join_path"), list) else [],
        "expected_shape": {"expected_tool": "v2_query_executor"},
        "success_label": bool(success),
        "source": "runtime_feedback",
        "notes": "auto_update_from_empty_result" if not success else "auto_update_from_success_result",
    }


# Alias cho backwards compat với service.py cũ
_build_runtime_learning_sample = build_runtime_learning_sample
