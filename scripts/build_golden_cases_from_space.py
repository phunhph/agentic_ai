from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class GoldenCase:
    query: str
    tags: list[str]
    expected_entities: list[str]


def _normalize(text: str) -> str:
    s = str(text or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _is_noise(text: str) -> bool:
    q = _normalize(text).lower()
    if not q:
        return True
    if q.startswith("[không có nội dung text"):
        return True
    # Ignore onboarding/boilerplate messages
    if "thanks for adding" in q or "quietly listening" in q:
        return True
    blocked_contains = [
        "@all",
        "nhờ ace",
        "lấy use case",
        "muốn làm gì cũng được",
        "test thôi",
        "không aplly vào db thật",
        "mention nó vào",
    ]
    return any(x in q for x in blocked_contains)


def _strip_mentions(text: str) -> str:
    q = _normalize(text)
    q = re.sub(r"@salentassist\b", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def _tag_query(q: str) -> list[str]:
    lowered = q.lower()
    tags: list[str] = []
    if any(x in lowered for x in ["chi tiết", "chi tiet", "thông tin", "thong tin", "là gì", "la gi"]):
        tags.append("detail")
    if any(x in lowered for x in ["danh sách", "danh sach", "liệt kê", "liet ke", "list"]):
        tags.append("list")
    if any(x in lowered for x in ["thống kê", "thong ke", "báo cáo", "bao cao", "so với", "compare"]):
        tags.append("aggregate")
    if any(x in lowered for x in ["todo", "cần làm", "can lam", "next action", "hôm nay", "hom nay", "tuần này", "tuan nay", "1 tuần", "1 tuan"]):
        tags.append("compass")
    if any(x in lowered for x in ["owner", "assignee", "của ", "cua "]):
        tags.append("owner_scope")
    if "@salentassist" in lowered:
        tags.append("explicit_mention")
    return tags


def build_golden_cases(space_messages_path: Path, limit: int = 160) -> list[GoldenCase]:
    try:
        raw = json.loads(space_messages_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []

    # Use runtime ingest logic (fast-path) to infer entities so the golden set
    # reflects real system interpretation, not a separate alias scan.
    from v2.ingest import ingest_query  # noqa
    cases: list[GoldenCase] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        text = row.get("text", "")
        if _is_noise(text):
            continue
        q = _strip_mentions(str(text))
        q = _normalize(q)
        if len(q) < 4:
            continue
        k = q.lower()
        if k in seen:
            continue
        seen.add(k)
        ing = ingest_query(q, role="DEFAULT")
        entities = list(ing.entities or [])
        tags = _tag_query(q)
        if not entities and not tags:
            continue
        cases.append(GoldenCase(query=q, tags=tags, expected_entities=entities))
        if len(cases) >= max(1, int(limit)):
            break
    return cases


def main() -> None:
    ap = argparse.ArgumentParser(description="Build golden benchmark cases from space_messages.json")
    ap.add_argument("--input", type=str, default="space_messages.json", help="Input space messages JSON file.")
    ap.add_argument("--limit", type=int, default=160, help="Max unique queries to keep.")
    ap.add_argument("--out", type=str, default="storage/golden_cases.json", help="Output golden cases path.")
    args = ap.parse_args()

    inp = (ROOT / str(args.input)).resolve()
    outp = (ROOT / str(args.out)).resolve()
    cases = build_golden_cases(inp, limit=max(1, int(args.limit)))
    payload: list[dict[str, Any]] = [
        {"query": c.query, "tags": c.tags, "expected_entities": c.expected_entities}
        for c in cases
    ]
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built golden cases: {len(payload)} -> {outp}")


if __name__ == "__main__":
    main()

