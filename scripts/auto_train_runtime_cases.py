from __future__ import annotations

import argparse
import json
import sys
import concurrent.futures
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import random
import re

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v2.service import run_v2_pipeline
from v2.metadata import MetadataProvider


@dataclass
class Scenario:
    name: str
    role: str
    lang: str
    queries: list[str]
    difficulty: str = "normal"


def now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def build_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="detail_and_followup_contact",
            role="DEFAULT",
            lang="vi",
            difficulty="normal",
            queries=[
                "danh sách contact",
                "chỉ lấy contact có account là Demo Account 1",
                "chi tiết contact Demo Contact 1",
            ],
        ),
        Scenario(
            name="detail_and_followup_contract",
            role="DEFAULT",
            lang="vi",
            difficulty="normal",
            queries=[
                "danh sách contract",
                "lọc danh sách chỉ lấy contract có account là Demo Account 1",
                "chi tiết contract Demo Contract 1",
            ],
        ),
        Scenario(
            name="detail_and_followup_opportunity",
            role="DEFAULT",
            lang="vi",
            difficulty="normal",
            queries=[
                "danh sách opportunity",
                "chỉ lấy opportunity thuộc account Demo Account 1",
                "chi tiết opportunity Demo Opportunity 1",
            ],
        ),
        Scenario(
            name="create_and_update_like",
            role="SENIOR",
            lang="vi",
            difficulty="hard",
            queries=[
                "cập nhật bant cho opportunity Demo Opportunity 1: budget 50000, authority vp, need crm, timeline q3",
                "chi tiết opportunity Demo Opportunity 1",
            ],
        ),
        Scenario(
            name="english_variants",
            role="DEFAULT",
            lang="en",
            difficulty="normal",
            queries=[
                "list accounts",
                "show contacts related to Demo Account 1",
                "details contract Demo Contract 1",
            ],
        ),
        Scenario(
            name="ambiguous_cases_for_clarify",
            role="JUNIOR",
            lang="vi",
            difficulty="easy",
            queries=[
                "xem giúp tôi",
                "lấy thông tin liên quan",
                "cho mình danh sách chung",
            ],
        ),
        Scenario(
            name="aggregate_like_requests",
            role="DEFAULT",
            lang="vi",
            difficulty="hard",
            queries=[
                "thống kê số lượng account hiện tại",
                "thống kê số lượng contract và opportunity",
                "thống kê số lượng account, contract, và opp cùng với doanh thu hiện tại",
            ],
        ),
        Scenario(
            name="mixed_noise_real_chat_vi",
            role="DEFAULT",
            lang="vi",
            difficulty="hard",
            queries=[
                "a ơi cho em xin danh sách account nha",
                "rồi lọc giùm em account demo account 1 với ạ",
                "ok lấy chi tiết account đó luôn",
            ],
        ),
        Scenario(
            name="cross_table_chain_requests",
            role="SENIOR",
            lang="vi",
            difficulty="hard",
            queries=[
                "lấy contract liên quan account Demo Account 1",
                "từ contract đó lấy opp liên quan",
                "xem chi tiết opp Demo Opportunity 1",
            ],
        ),
        Scenario(
            name="choice_filter_requests",
            role="DEFAULT",
            lang="vi",
            difficulty="hard",
            queries=[
                "lọc account theo market Japan",
                "lọc account theo action class 135150003",
                "thống kê account theo status active",
            ],
        ),
        Scenario(
            name="owner_filter_requests",
            role="DEFAULT",
            lang="vi",
            difficulty="hard",
            queries=[
                "lọc contact theo assignee",
                "lọc contract theo assignee",
                "lọc opportunity theo owner",
            ],
        ),
        Scenario(
            name="linked_table_navigation",
            role="SENIOR",
            lang="vi",
            difficulty="hard",
            queries=[
                "lấy contact liên quan account Demo Account 1",
                "từ contact đó lấy contract liên quan",
                "chi tiết contract đầu tiên",
            ],
        ),
    ]


def _normalize_space_query(text: str) -> str:
    q = str(text or "").strip()
    q = re.sub(r"\s+", " ", q)
    return q


def _is_noise_space_query(text: str) -> bool:
    q = _normalize_space_query(text).lower()
    if not q:
        return True
    if q.startswith("[không có nội dung text"):
        return True
    # Ignore broad room/test orchestration messages.
    blocked_contains = [
        "@all",
        "nhờ ace",
        "lấy use case",
        "muốn làm gì cũng được",
        "test thôi",
        "không aplly vào db thật",
        "mention nó vào",
        "vẫn đang gà lắm",
        "thôi được rồi",
        "đệt",
    ]
    return any(x in q for x in blocked_contains)


def _strip_agent_mentions(text: str) -> str:
    q = _normalize_space_query(text)
    q = re.sub(r"@salentassist\b", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def load_space_message_queries(path: Path, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(rows, list):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("text", "")
        if _is_noise_space_query(str(raw)):
            continue
        clean = _strip_agent_mentions(str(raw))
        clean = _normalize_space_query(clean)
        if not clean or len(clean) < 4:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= max(1, int(limit)):
            break
    return out


def build_space_message_scenarios(path: Path, query_limit: int = 80, chunk_size: int = 3) -> list[Scenario]:
    queries = load_space_message_queries(path=path, limit=query_limit)
    if not queries:
        return []
    chunks: list[Scenario] = []
    size = max(1, int(chunk_size))
    for i in range(0, len(queries), size):
        block = queries[i:i + size]
        if not block:
            continue
        chunks.append(
            Scenario(
                name=f"space_messages_real_case_{(i // size) + 1}",
                role="DEFAULT",
                lang="vi",
                difficulty="hard",
                queries=block,
            )
        )
    return chunks


def build_generated_scenarios(max_generated: int = 6) -> list[Scenario]:
    provider = MetadataProvider()
    aliases = provider.iter_alias_items()
    generated: list[Scenario] = []
    seen_tables: set[str] = set()
    for alias, table in aliases:
        a = str(alias or "").strip().lower()
        t = str(table or "").strip()
        if not a or not t:
            continue
        if a.startswith(("hbl_", "cr987_", "mc_")):
            continue
        if " " in a:
            continue
        if t in seen_tables:
            continue
        seen_tables.add(t)
        clean = t.replace("hbl_", "")
        generated.append(
            Scenario(
                name=f"generated_{clean}",
                role="DEFAULT",
                lang="vi",
                difficulty="normal",
                queries=[
                    f"danh sách {a}",
                    f"chi tiết {a} Demo {clean} 1",
                    f"lấy {a} liên quan account Demo Account 1",
                ],
            )
        )
        if len(generated) >= max(1, max_generated):
            break
    return generated


def mine_failure_queries(limit: int = 12) -> list[str]:
    log_dir = ROOT / "storage" / "v2" / "training" / "auto_train_logs"
    if not log_dir.exists():
        return []
    log_files = sorted(log_dir.glob("auto_train_runtime_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    failures: list[str] = []
    for path in log_files[:4]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            summary = row.get("summary", {}) if isinstance(row.get("summary"), dict) else {}
            query = str(row.get("query", "")).strip()
            if not query:
                continue
            trusted = bool(summary.get("trusted", False))
            decision_state = str(summary.get("decision_state", "")).strip()
            result_count = int(summary.get("result_count", 0) or 0)
            if (not trusted) or decision_state == "ask_clarify" or result_count == 0:
                failures.append(query)
            if len(failures) >= limit:
                break
        if len(failures) >= limit:
            break
    # Keep unique but preserve first-seen order.
    uniq: list[str] = []
    seen: set[str] = set()
    for q in failures:
        k = q.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(q)
    return uniq[:limit]


def summarize_record(result: dict[str, Any]) -> dict[str, Any]:
    trust_gate = result.get("trust_gate", {}) if isinstance(result.get("trust_gate"), dict) else {}
    learning_update = result.get("learning_update", {}) if isinstance(result.get("learning_update"), dict) else {}
    appended = learning_update.get("appended_sample", {}) if isinstance(learning_update.get("appended_sample"), dict) else {}
    firewall_event = learning_update.get("firewall_event", {}) if isinstance(learning_update.get("firewall_event"), dict) else {}
    return {
        "decision_state": result.get("decision_state"),
        "trusted": bool(trust_gate.get("trusted", False)),
        "plan_validation_ok": bool(trust_gate.get("plan_validation_ok", False)),
        "plan_validation_errors": trust_gate.get("plan_validation_errors", []),
        "result_count": len(result.get("result", [])) if isinstance(result.get("result"), list) else 0,
        "learning_decision": learning_update.get("learning_decision"),
        "learning_phase": learning_update.get("learning_phase"),
        "learning_reason": appended.get("reason"),
        "firewall_decision": firewall_event.get("decision"),
        "firewall_scores": firewall_event.get("gate_scores", {}),
        "plan_root": (result.get("execution_plan") or {}).get("root_table"),
    }


def _run_pipeline_with_timeout(query: str, role: str, session_id: str, lang: str, timeout_seconds: int) -> dict[str, Any]:
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = ex.submit(run_v2_pipeline, query, role=role, session_id=session_id, lang=lang)
        return fut.result(timeout=max(1, int(timeout_seconds)))
    except concurrent.futures.TimeoutError as exc:
        fut.cancel()
        # Do not wait for blocked worker thread on timeout.
        ex.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError(f"pipeline_timeout_after_{max(1, int(timeout_seconds))}s") from exc
    finally:
        # Normal path: release executor resources.
        ex.shutdown(wait=False, cancel_futures=True)


def _variants_for_query(query: str) -> list[str]:
    q = str(query or "").strip()
    if not q:
        return []
    variants = {
        q,
        q.lower(),
        q.replace("  ", " "),
        q + " nhé",
        q + " giúp mình",
    }
    # Common VI shorthand/noise patterns
    variants.add(q.replace("không", "k").replace("được", "dc"))
    variants.add(q.replace("thống kê", "tk").replace("số lượng", "sl"))
    # EN shorthand patterns
    variants.add(q.replace("details", "detail").replace("show", "list"))
    return [v for v in variants if v.strip()]


def run(
    rounds: int,
    max_scenarios: int | None = None,
    scenario_offset: int = 0,
    variant_factor: int = 2,
    seed: int = 42,
    auto_generate: bool = True,
    auto_retry_failures: bool = True,
    timeout_seconds: int = 20,
    space_cases_file: Path | None = None,
    space_case_limit: int = 80,
) -> tuple[Path, Path]:
    scenarios = build_scenarios()
    generated_count = 0
    mined_failure_count = 0
    space_scenarios_count = 0
    space_queries_count = 0
    if space_cases_file is not None:
        space_scenarios = build_space_message_scenarios(
            path=space_cases_file,
            query_limit=max(1, int(space_case_limit)),
            chunk_size=3,
        )
        if space_scenarios:
            scenarios.extend(space_scenarios)
            space_scenarios_count = len(space_scenarios)
            space_queries_count = sum(len(s.queries) for s in space_scenarios)
    if auto_generate:
        generated = build_generated_scenarios(max_generated=6)
        scenarios.extend(generated)
        generated_count = len(generated)
    if auto_retry_failures:
        failure_queries = mine_failure_queries(limit=12)
        if failure_queries:
            scenarios.append(
                Scenario(
                    name="mined_failures_retry",
                    role="DEFAULT",
                    lang="vi",
                    difficulty="hard",
                    queries=failure_queries,
                )
            )
            mined_failure_count = len(failure_queries)
    offset = max(0, int(scenario_offset))
    if offset > 0:
        scenarios = scenarios[offset:]
    if max_scenarios is not None:
        scenarios = scenarios[: max(0, max_scenarios)]
    random.seed(seed)

    out_dir = ROOT / "storage" / "v2" / "training" / "auto_train_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = now_tag()
    log_path = out_dir / f"auto_train_runtime_{tag}.jsonl"
    summary_path = out_dir / f"auto_train_runtime_{tag}_summary.json"

    total = 0
    auto_execute = 0
    ask_clarify = 0
    trusted = 0
    learned = 0
    skipped = 0
    firewall_counts = {"allow": 0, "quarantine": 0, "reject": 0}
    difficulty_counts: dict[str, int] = {"easy": 0, "normal": 0, "hard": 0}

    with log_path.open("w", encoding="utf-8") as f:
        for r in range(rounds):
            for idx, scenario in enumerate(scenarios, start=1):
                session_id = f"auto-train-{scenario.name}-r{r+1}"
                for step, query in enumerate(scenario.queries, start=1):
                    variants = _variants_for_query(query)
                    random.shuffle(variants)
                    picked = variants[: max(1, variant_factor)]
                    for v_idx, qv in enumerate(picked, start=1):
                        total += 1
                        difficulty_counts[scenario.difficulty] = difficulty_counts.get(scenario.difficulty, 0) + 1
                        ts = datetime.now(UTC).isoformat()
                        try:
                            result = _run_pipeline_with_timeout(
                                qv,
                                role=scenario.role,
                                session_id=session_id,
                                lang=scenario.lang,
                                timeout_seconds=timeout_seconds,
                            )
                            summary = summarize_record(result)
                            decision_state = str(summary.get("decision_state", ""))
                            if decision_state == "auto_execute":
                                auto_execute += 1
                            if decision_state == "ask_clarify":
                                ask_clarify += 1
                            if bool(summary.get("trusted", False)):
                                trusted += 1
                            if str(summary.get("learning_decision", "")) == "appended":
                                learned += 1
                            else:
                                skipped += 1
                            fw = str(summary.get("firewall_decision", "")).strip().lower()
                            if fw in firewall_counts:
                                firewall_counts[fw] += 1
                            record = {
                                "ts": ts,
                                "round": r + 1,
                                "scenario_index": idx,
                                "scenario_name": scenario.name,
                                "difficulty": scenario.difficulty,
                                "step": step,
                                "variant_index": v_idx,
                                "session_id": session_id,
                                "query": qv,
                                "query_base": query,
                                "role": scenario.role,
                                "lang": scenario.lang,
                                "status": "ok",
                                "summary": summary,
                            }
                        except Exception as exc:
                            record = {
                                "ts": ts,
                                "round": r + 1,
                                "scenario_index": idx,
                                "scenario_name": scenario.name,
                                "difficulty": scenario.difficulty,
                                "step": step,
                                "variant_index": v_idx,
                                "session_id": session_id,
                                "query": qv,
                                "query_base": query,
                                "role": scenario.role,
                                "lang": scenario.lang,
                                "status": "error",
                                "error": str(exc),
                            }
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "rounds": rounds,
        "scenario_count": len(scenarios),
        "generated_scenarios": generated_count,
        "space_message_scenarios": space_scenarios_count,
        "space_message_queries": space_queries_count,
        "mined_failure_queries": mined_failure_count,
        "query_runs": total,
        "variant_factor": variant_factor,
        "decision_distribution": {
            "auto_execute": auto_execute,
            "ask_clarify": ask_clarify,
        },
        "difficulty_distribution": difficulty_counts,
        "trusted_runs": trusted,
        "learning": {
            "appended": learned,
            "skipped_or_blocked": skipped,
        },
        "firewall_decisions": firewall_counts,
        "log_file": str(log_path),
    }
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return log_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-run runtime cases for learning and supervision logs.")
    parser.add_argument("--rounds", type=int, default=2, help="How many rounds to run through all scenarios.")
    parser.add_argument("--max-scenarios", type=int, default=None, help="Optional limit for scenario count.")
    parser.add_argument("--scenario-offset", type=int, default=0, help="Offset in scenario list for chunked runs.")
    parser.add_argument("--variant-factor", type=int, default=2, help="How many linguistic variants per base query.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for variant sampling.")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="Timeout per runtime query.")
    parser.add_argument(
        "--space-cases-file",
        type=str,
        default="space_messages.json",
        help="Path to real chat use-cases file (JSON list of messages).",
    )
    parser.add_argument(
        "--space-case-limit",
        type=int,
        default=80,
        help="Maximum unique real-chat queries to import from space cases file.",
    )
    parser.add_argument("--no-auto-generate", action="store_true", help="Disable auto-generated scenarios from metadata aliases.")
    parser.add_argument("--no-auto-retry-failures", action="store_true", help="Disable retrying mined failure queries from recent logs.")
    args = parser.parse_args()

    rounds = max(1, int(args.rounds))
    max_scenarios = int(args.max_scenarios) if args.max_scenarios is not None else None
    variant_factor = max(1, int(args.variant_factor))
    seed = int(args.seed)
    log_path, summary_path = run(
        rounds=rounds,
        max_scenarios=max_scenarios,
        scenario_offset=max(0, int(args.scenario_offset)),
        variant_factor=variant_factor,
        seed=seed,
        auto_generate=not bool(args.no_auto_generate),
        auto_retry_failures=not bool(args.no_auto_retry_failures),
        timeout_seconds=max(10, int(args.timeout_seconds)),
        space_cases_file=(ROOT / str(args.space_cases_file)).resolve(),
        space_case_limit=max(1, int(args.space_case_limit)),
    )
    print(f"Auto-train run complete.\n- Log: {log_path}\n- Summary: {summary_path}")


if __name__ == "__main__":
    main()

