from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynamic_metadata.eval_runner import run_eval
from dynamic_metadata.paths import dynamic_cases_path, dynamic_eval_report_path


def main() -> None:
    root = ROOT_DIR
    seeded_path = dynamic_cases_path()
    if seeded_path.exists():
        cases = json.loads(seeded_path.read_text(encoding="utf-8"))
    else:
        messages_path = root / "space_messages.json"
        messages = json.loads(messages_path.read_text(encoding="utf-8")) if messages_path.exists() else []
        cases = [{"query": str(m.get("text", "")), "expected_tool": None} for m in messages if str(m.get("text", "")).strip()]

    report = run_eval(cases)
    out = dynamic_eval_report_path()
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Evaluated {report['total_cases']} cases -> {out}")
    print(
        "tool_accuracy={:.2f} path_resolution_success={:.2f} choice_constraint_success={:.2f}".format(
            report["tool_accuracy"], report["path_resolution_success"], report["choice_constraint_success"]
        )
    )


if __name__ == "__main__":
    main()
