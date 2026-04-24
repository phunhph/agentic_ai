from __future__ import annotations

import json
import re
from pathlib import Path

from v2.learn.firewall import redact_runtime_sample

TRAINSET_PATH = Path("storage/v2/matrix/trainset_v2.jsonl")
CASES_PATH = Path("storage/dynamic_cases.json")
LEARNING_PHASE = "phase_understanding_v2"


def bootstrap_trainset_from_cases() -> int:
    TRAINSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CASES_PATH.exists():
        return 0
    raw = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else []
    written = 0
    with TRAINSET_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            if not isinstance(row, dict):
                continue
            sample = {
                "normalized_query": str(row.get("query", "")).strip().lower(),
                "intent": str(row.get("intent", "unknown")).strip().lower(),
                "root_table": str(row.get("root_table", "hbl_account")).strip(),
                "entities": row.get("expected_entities", []),
                "filters": row.get("filters", []),
                "join_plan": row.get("join_plan", []),
                "expected_shape": {"expected_tool": row.get("expected_tool")},
                "success_label": bool(row.get("success", False)),
            }
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            written += 1
    return written


def append_trainset_sample(sample: dict) -> dict:
    TRAINSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TRAINSET_PATH.exists():
        TRAINSET_PATH.write_text("", encoding="utf-8")

    normalized_query = str(sample.get("normalized_query", "")).strip().lower()
    normalized_query = re.sub(r"\s+", " ", normalized_query)
    intent = str(sample.get("intent", "unknown")).strip().lower()
    root_table = str(sample.get("root_table", "hbl_account")).strip() or "hbl_account"
    entities = sample.get("entities", []) if isinstance(sample.get("entities"), list) else []
    filters = sample.get("filters", []) if isinstance(sample.get("filters"), list) else []
    join_plan = sample.get("join_plan", []) if isinstance(sample.get("join_plan"), list) else []
    expected_shape = sample.get("expected_shape", {})
    if not isinstance(expected_shape, dict):
        expected_shape = {}
    expected_tool = str(expected_shape.get("expected_tool", "v2_query_executor")).strip() or "v2_query_executor"
    success_label = bool(sample.get("success_label", False))
    filter_fields = []
    for f in filters:
        if isinstance(f, dict) and f.get("field"):
            filter_fields.append(str(f.get("field")).strip().lower())
    filter_fields = sorted(set(filter_fields))
    entities = sorted(set(str(e).strip().lower() for e in entities if str(e).strip()))
    query_template = re.sub(r"\b\d+\b", "<num>", normalized_query)
    query_template = re.sub(r"\"[^\"]+\"|'[^']+'", "<text>", query_template)
    # Normalize high-variance phrases to semantic placeholders.
    query_template = re.sub(r"\bdemo\s+[a-z]+\s*<num>\b", "<entity_name>", query_template)
    query_template = re.sub(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", "<email>", query_template)
    query_template = re.sub(r"\b\d{8,}\b", "<id>", query_template)
    query_semantic_template = str(sample.get("query_semantic_template", "")).strip().lower()
    if not query_semantic_template:
        query_semantic_template = query_template
    join_targets = sorted(
        {
            str(j.get("to_table", "")).strip().lower()
            for j in join_plan
            if isinstance(j, dict) and str(j.get("to_table", "")).strip()
        }
    )
    signature = "|".join(
        [
            f"intent:{intent}",
            f"root:{root_table.lower()}",
            f"entities:{','.join(entities)}",
            f"filters:{','.join(filter_fields)}",
            f"joins:{len(join_plan)}",
            f"tool:{expected_tool.lower()}",
        ]
    )
    semantic_signature = "|".join(
        [
            f"intent:{intent}",
            f"root:{root_table.lower()}",
            f"entities:{','.join(entities)}",
            f"filters:{','.join(filter_fields)}",
            f"join_targets:{','.join(join_targets)}",
            f"tool:{expected_tool.lower()}",
            f"semantic:{query_semantic_template}",
        ]
    )

    # Anti-rote gate: reject low-information samples that only mirror raw text.
    if intent in {"", "unknown"} and not entities and not filter_fields:
        return {
            "status": "skipped",
            "reason": "low_information_sample",
            "signature": signature,
        }

    existing_rows = []
    for line in TRAINSET_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            existing_rows.append(row)
    same_signature_rows = [r for r in existing_rows if str(r.get("signature", "")).strip() == signature]
    for row in same_signature_rows:
        if bool(row.get("success_label", False)) == success_label:
            return {
                "status": "skipped",
                "reason": "duplicate_signature_same_outcome",
                "signature": signature,
            }
    # Anti-rote semantic gate: if semantic template already learned for same
    # intent+root and same outcome, skip to avoid memorizing surface wording.
    same_semantic_rows = [
        r
        for r in existing_rows
        if str(r.get("intent", "")).strip().lower() == intent
        and str(r.get("root_table", "")).strip().lower() == root_table.lower()
        and str(r.get("query_template", "")).strip().lower() == query_template
    ]
    for row in same_semantic_rows:
        if bool(row.get("success_label", False)) == success_label:
            return {
                "status": "skipped",
                "reason": "duplicate_semantic_template_same_outcome",
                "signature": signature,
                "query_template": query_template,
            }
    same_semantic_signature_rows = [
        r
        for r in existing_rows
        if str(r.get("semantic_signature", "")).strip().lower() == semantic_signature
    ]
    for row in same_semantic_signature_rows:
        if bool(row.get("success_label", False)) == success_label:
            return {
                "status": "skipped",
                "reason": "duplicate_semantic_signature_same_outcome",
                "signature": signature,
                "semantic_signature": semantic_signature,
            }

    learning_mode = "new_signature"
    if same_signature_rows:
        learning_mode = "contradiction_update"
    elif same_semantic_rows:
        learning_mode = "semantic_variant"
    elif same_semantic_signature_rows:
        learning_mode = "semantic_stable_noop"
    elif any(str(r.get("intent", "")).strip().lower() == intent for r in existing_rows):
        learning_mode = "intent_expansion"

    payload = {
        "normalized_query": normalized_query,
        "query_template": query_template,
        "query_semantic_template": query_semantic_template,
        "intent": intent,
        "root_table": root_table,
        "entities": entities,
        "filters": filters,
        "join_plan": join_plan,
        "expected_shape": {"expected_tool": expected_tool},
        "success_label": success_label,
        "signature": signature,
        "semantic_signature": semantic_signature,
        "source": str(sample.get("source", "runtime_feedback")).strip() or "runtime_feedback",
        "notes": str(sample.get("notes", "")).strip(),
        "learning_mode": learning_mode,
        "learning_phase": LEARNING_PHASE,
    }
    payload = redact_runtime_sample(payload)
    payload["query_template"] = query_template
    payload["intent"] = intent
    payload["root_table"] = root_table
    payload["entities"] = entities
    payload["join_plan"] = join_plan
    payload["expected_shape"] = {"expected_tool": expected_tool}
    payload["success_label"] = success_label
    payload["signature"] = signature
    payload["semantic_signature"] = semantic_signature
    payload["source"] = str(sample.get("source", "runtime_feedback")).strip() or "runtime_feedback"
    payload["notes"] = str(sample.get("notes", "")).strip()
    payload["learning_mode"] = learning_mode
    payload["learning_phase"] = LEARNING_PHASE
    with TRAINSET_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return {"status": "appended", **payload}
