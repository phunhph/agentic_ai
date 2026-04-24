from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LOG_PATH = Path("storage/v2/firewall/trust_firewall_log_v2.jsonl")
QUARANTINE_PATH = Path("storage/v2/firewall/quarantine_learning_v2.jsonl")
EVAL_PATH = Path("storage/v2/firewall/trust_firewall_eval_v2.json")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def redact_runtime_sample(sample: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(sample or {})
    redacted["normalized_query_hash"] = _sha(str(sample.get("normalized_query", "")))
    redacted.pop("normalized_query", None)
    filters = redacted.get("filters", [])
    cleaned_filters: list[dict[str, Any]] = []
    if isinstance(filters, list):
        for f in filters:
            if not isinstance(f, dict):
                continue
            cleaned_filters.append(
                {
                    "field": str(f.get("field", "")).strip(),
                    "op": str(f.get("op", "")).strip(),
                    "value": "<redacted>",
                }
            )
    redacted["filters"] = cleaned_filters
    return redacted


def evaluate_firewall(sample: dict[str, Any], ingest_layer: dict[str, Any], execution_trace: dict[str, Any]) -> dict[str, Any]:
    has_entities = bool(ingest_layer.get("entities"))
    has_filters = bool(ingest_layer.get("request_filters"))
    ambiguity = float(ingest_layer.get("ambiguity_score", 1.0) or 1.0)
    guardrail = execution_trace.get("guardrail", {}) if isinstance(execution_trace, dict) else {}
    guardrail_ok = bool(isinstance(guardrail, dict) and guardrail.get("ok", False))

    signal_quality = 0.0
    signal_quality += 0.35 if has_entities else 0.0
    signal_quality += 0.35 if has_filters else 0.0
    signal_quality += 0.3 if guardrail_ok else 0.0
    signal_quality = round(max(0.0, min(1.0, signal_quality)), 4)

    privacy_risk = 0.0
    for f in (sample.get("filters", []) if isinstance(sample.get("filters"), list) else []):
        if isinstance(f, dict) and f.get("value") not in (None, "", "<redacted>"):
            privacy_risk += 0.25
    privacy_risk = round(max(0.0, min(1.0, privacy_risk)), 4)

    poisoning_risk = round(max(0.0, min(1.0, ambiguity)), 4)

    if signal_quality < 0.45 or poisoning_risk > 0.9:
        decision = "reject"
        reasons = ["low_signal_or_high_poisoning"]
    elif privacy_risk > 0.5 or poisoning_risk > 0.65:
        decision = "quarantine"
        reasons = ["privacy_or_poisoning_risk"]
    else:
        decision = "allow"
        reasons = []

    return {
        "event_id": str(uuid4()),
        "ts": _now_iso(),
        "gate_scores": {
            "signal_quality": signal_quality,
            "privacy_risk": privacy_risk,
            "poisoning_risk": poisoning_risk,
        },
        "decision": decision,
        "reasons": reasons,
        "policy": {"min_signal_quality": 0.45, "max_privacy_risk": 0.5, "max_poisoning_risk": 0.65},
    }


def log_firewall_event(entry: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def quarantine_sample(entry: dict[str, Any], sample: dict[str, Any]) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "quarantine_id": str(uuid4()),
        "ts": _now_iso(),
        "firewall_event_id": entry.get("event_id"),
        "decision": entry.get("decision"),
        "reasons": entry.get("reasons", []),
        "sample_redacted": redact_runtime_sample(sample),
        "review_status": "pending",
    }
    with QUARANTINE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def refresh_firewall_eval() -> dict[str, Any]:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts = {"allow": 0, "quarantine": 0, "reject": 0}
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            decision = str(row.get("decision", "")).strip().lower()
            if decision in counts:
                counts[decision] += 1
    total = max(1, sum(counts.values()))
    report = {
        "version": f"v2-firewall-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        "evaluated_at": _now_iso(),
        "counts": counts,
        "rates": {
            "quarantine_rate": round(counts["quarantine"] / total, 4),
            "reject_rate": round(counts["reject"] / total, 4),
        },
        "pass": counts["reject"] / total < 0.4,
    }
    EVAL_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
