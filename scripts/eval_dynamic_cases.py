from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.dynamic_planner import plan_with_metadata


def run_eval(cases: list[dict]) -> dict:
    total = len(cases)
    tool_ok = 0
    entity_path_ok = 0
    choice_ok = 0
    knowledge_reuse_hit = 0
    rows: list[dict] = []

    for case in cases:
        state = {"goal": case["query"], "role": "BUYER", "domain": "general", "history": []}
        knowledge_hits = case.get("knowledge_hits") if isinstance(case.get("knowledge_hits"), list) else []
        decision = plan_with_metadata(state, knowledge_hits=knowledge_hits)
        trace = decision.get("trace", {})

        tool_match = decision.get("tool") == case.get("expected_tool")
        tool_ok += int(tool_match)

        path_match = True
        if case.get("expected_entities"):
            selected = trace.get("selected_entities", [])
            path_match = all(e in selected for e in case["expected_entities"])
        entity_path_ok += int(path_match)

        choice_match = True
        if case.get("choice_group"):
            constraints = trace.get("choice_constraints", [])
            choice_match = any(c.get("choice_group") == case["choice_group"] for c in constraints)
        choice_ok += int(choice_match)
        if knowledge_hits and decision.get("tool") == case.get("expected_tool"):
            knowledge_reuse_hit += 1

        rows.append(
            {
                "query": case["query"],
                "tool": decision.get("tool"),
                "tool_match": tool_match,
                "path_match": path_match,
                "choice_match": choice_match,
                "trace": trace,
            }
        )

    return {
        "total_cases": total,
        "tool_accuracy": (tool_ok / total) if total else 0.0,
        "path_resolution_success": (entity_path_ok / total) if total else 0.0,
        "choice_constraint_success": (choice_ok / total) if total else 0.0,
        "correction_reuse_hit_rate": (knowledge_reuse_hit / total) if total else 0.0,
        "rows": rows,
    }


def main() -> None:
    root = ROOT_DIR
    seeded_path = root / "storage" / "dynamic_cases.json"
    if seeded_path.exists():
        cases = json.loads(seeded_path.read_text(encoding="utf-8"))
    else:
        messages_path = root / "space_messages.json"
        messages = json.loads(messages_path.read_text(encoding="utf-8")) if messages_path.exists() else []
        cases = [{"query": str(m.get("text", "")), "expected_tool": None} for m in messages if str(m.get("text", "")).strip()]

    report = run_eval(cases)
    out = root / "storage" / "dynamic_eval_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Evaluated {report['total_cases']} cases -> {out}")
    print(
        "tool_accuracy={:.2f} path_resolution_success={:.2f} choice_constraint_success={:.2f}".format(
            report["tool_accuracy"], report["path_resolution_success"], report["choice_constraint_success"]
        )
    )


if __name__ == "__main__":
    main()

