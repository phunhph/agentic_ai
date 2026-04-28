from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ingest_worker(query: str, queue: Any) -> None:
    from v2.ingest import ingest_query

    result = ingest_query(query, role="DEFAULT")
    queue.put(
        {
            "intent": result.intent,
            "entities": list(result.entities or []),
            "ambiguity_score": result.ambiguity_score,
        }
    )


def _run_ingest_with_timeout(query: str, timeout_seconds: int) -> dict[str, Any]:
    queue: Any = mp.Queue()
    proc = mp.Process(target=_ingest_worker, args=(query, queue))
    proc.start()
    proc.join(timeout=max(1, int(timeout_seconds)))
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=2)
        raise TimeoutError(f"ingest_timeout_after_{timeout_seconds}s")
    if not queue.empty():
        return dict(queue.get())
    raise RuntimeError("ingest_worker_returned_no_result")


def evaluate_cases(path: Path, limit: int | None = None, timeout_seconds: int = 8) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else []
    if limit is not None:
        rows = rows[: max(0, int(limit))]

    total = 0
    passed = 0
    skipped = 0
    details: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        query = str(row.get("query", "")).strip()
        expected_entities = sorted(str(x).strip() for x in (row.get("expected_entities") or []) if str(x).strip())
        tags = list(row.get("tags") or [])
        if not query:
            continue
        total += 1
        try:
            actual = _run_ingest_with_timeout(query, timeout_seconds=timeout_seconds)
            actual_entities = sorted(str(x).strip() for x in (actual.get("entities") or []) if str(x).strip())
            actual_intent = str(actual.get("intent", "")).strip()
            actual_ambiguity = actual.get("ambiguity_score")
        except Exception as exc:
            details.append(
                {
                    "query": query,
                    "tags": tags,
                    "status": "error",
                    "error": str(exc),
                    "expected_entities": expected_entities,
                }
            )
            continue

        if not expected_entities:
            skipped += 1
            details.append(
                {
                    "query": query,
                    "tags": tags,
                    "status": "skipped_no_expected_entities",
                    "actual_entities": actual_entities,
                    "intent": actual_intent,
                    "ambiguity_score": actual_ambiguity,
                }
            )
            continue

        ok = set(expected_entities).issubset(set(actual_entities))
        if ok:
            passed += 1
        details.append(
            {
                "query": query,
                "tags": tags,
                "status": "pass" if ok else "fail",
                "expected_entities": expected_entities,
                "actual_entities": actual_entities,
                "intent": actual_intent,
                "ambiguity_score": actual_ambiguity,
            }
        )

    evaluated = max(0, total - skipped)
    pass_rate = round((passed / evaluated), 4) if evaluated else 0.0
    return {
        "total_cases": total,
        "evaluated_cases": evaluated,
        "skipped_cases": skipped,
        "passed_cases": passed,
        "pass_rate": pass_rate,
        "details": details,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate parser understanding against golden cases.")
    ap.add_argument("--input", type=str, default="storage/golden_cases.json", help="Golden cases JSON path.")
    ap.add_argument("--limit", type=int, default=None, help="Optional limit of cases to evaluate.")
    ap.add_argument(
        "--out",
        type=str,
        default="storage/golden_cases_eval.json",
        help="Output evaluation report path.",
    )
    ap.add_argument("--timeout-seconds", type=int, default=8, help="Per-case ingest timeout.")
    args = ap.parse_args()

    inp = (ROOT / str(args.input)).resolve()
    outp = (ROOT / str(args.out)).resolve()
    report = evaluate_cases(inp, limit=args.limit, timeout_seconds=max(1, int(args.timeout_seconds)))
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Golden eval complete: pass={report['passed_cases']}/{report['evaluated_cases']} "
        f"(rate={report['pass_rate']}) -> {outp}"
    )


if __name__ == "__main__":
    main()

