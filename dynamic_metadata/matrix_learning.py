from __future__ import annotations

import json
from typing import Any

from dynamic_metadata.case_memory import load_cases
from dynamic_metadata.case_seed import build_cases
from dynamic_metadata.eval_runner import run_eval
from dynamic_metadata.learning_schema import LearnedCase
from dynamic_metadata.paths import dynamic_cases_path, dynamic_eval_report_path
from dynamic_metadata.text_normalize import normalize_goal_text


def _read_cases() -> list[dict[str, Any]]:
    path = dynamic_cases_path()
    if not path.exists():
        seeded = build_cases()
        _write_cases(seeded)
        return seeded
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def _write_cases(cases: list[dict[str, Any]]) -> None:
    path = dynamic_cases_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        load_cases.cache_clear()
    except Exception:
        pass


def _extract_expected_entities(trace: dict[str, Any]) -> list[str]:
    entities = trace.get("selected_entities", [])
    if not isinstance(entities, list):
        return []
    out: list[str] = []
    for e in entities:
        v = str(e).strip()
        if v and v not in out:
            out.append(v)
    return out


def _extract_target_identities(trace: dict[str, Any]) -> list[dict[str, Any]]:
    identities = trace.get("target_identities", [])
    if not isinstance(identities, list):
        return []
    out: list[dict[str, Any]] = []
    for item in identities:
        if not isinstance(item, dict):
            continue
        t = str(item.get("type", "")).strip()
        if not t:
            continue
        out.append(
            {
                "type": t,
                "id": str(item.get("id", "")).strip() or None,
                "name": str(item.get("name", "")).strip() or None,
                "field": str(item.get("field", "")).strip() or None,
                "confidence": float(item.get("confidence", 1.0) or 1.0),
            }
        )
    return out


def upsert_case_from_run(
    *,
    query: str,
    expected_tool: str,
    trace: dict[str, Any] | None,
    success: bool,
) -> dict[str, Any]:
    trace = trace if isinstance(trace, dict) else {}
    normalized = normalize_goal_text(query)
    if not normalized or not expected_tool:
        return {"updated": False, "reason": "missing_query_or_tool"}

    cases = _read_cases()
    expected_entities = _extract_expected_entities(trace)
    target_identities = _extract_target_identities(trace)
    choice_constraints = trace.get("choice_constraints", [])
    choice_group = None
    choice_label = None
    if isinstance(choice_constraints, list) and choice_constraints:
        c0 = choice_constraints[0] if isinstance(choice_constraints[0], dict) else {}
        choice_group = c0.get("choice_group")
        choice_label = c0.get("choice_label")

    idx = -1
    for i, c in enumerate(cases):
        if normalize_goal_text(str(c.get("query", ""))) == normalized:
            idx = i
            break

    planner_mode = str(trace.get("planner_mode", "")).strip()
    if idx >= 0:
        row = dict(cases[idx])
        row["expected_tool"] = expected_tool
        if expected_entities:
            row["expected_entities"] = expected_entities
        if target_identities:
            row["target_identities"] = target_identities
        if choice_group:
            row["choice_group"] = choice_group
        if choice_label:
            row["choice_label"] = choice_label
        row["usage_count"] = int(row.get("usage_count", 0)) + 1
        row["success_count"] = int(row.get("success_count", 0)) + int(bool(success))
        row["last_success"] = bool(success)
        if planner_mode:
            row["planner_mode"] = planner_mode
        cases[idx] = LearnedCase(
            query=str(row.get("query", query)),
            expected_tool=str(row.get("expected_tool", expected_tool)),
            expected_entities=row.get("expected_entities") if isinstance(row.get("expected_entities"), list) else [],
            target_identities=row.get("target_identities") if isinstance(row.get("target_identities"), list) else [],
            usage_count=int(row.get("usage_count", 0)),
            success_count=int(row.get("success_count", 0)),
            last_success=bool(row.get("last_success", False)),
            planner_mode=str(row.get("planner_mode", "")),
        ).to_dict()
        _write_cases(cases)
        return {"updated": True, "created": False, "index": idx}

    new_case = LearnedCase(
        query=query,
        expected_tool=expected_tool,
        expected_entities=expected_entities,
        target_identities=target_identities,
        usage_count=1,
        success_count=int(bool(success)),
        last_success=bool(success),
        planner_mode=planner_mode,
    ).to_dict()
    if choice_group:
        new_case["choice_group"] = choice_group
    if choice_label:
        new_case["choice_label"] = choice_label
    cases.append(new_case)
    _write_cases(cases)
    return {"updated": True, "created": True, "index": len(cases) - 1}


def penalize_case(query: str, *, amount: int = 1) -> dict[str, Any]:
    normalized = normalize_goal_text(query)
    if not normalized:
        return {"updated": False, "reason": "empty_query"}
    cases = _read_cases()
    for i, c in enumerate(cases):
        if normalize_goal_text(str(c.get("query", ""))) != normalized:
            continue
        row = dict(c)
        row["usage_count"] = int(row.get("usage_count", 0)) + max(1, amount)
        # negative reinforcement: keep success_count unchanged (or decrement softly)
        row["success_count"] = max(0, int(row.get("success_count", 0)) - 1)
        row["last_success"] = False
        cases[i] = row
        _write_cases(cases)
        return {"updated": True, "index": i}
    return {"updated": False, "reason": "case_not_found"}


def refresh_matrix_eval_report() -> dict[str, Any]:
    cases = _read_cases()
    report = run_eval(cases)
    out = dynamic_eval_report_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

