"""
phase4_execute/fk_resolver.py
Tách từ v2/service.py — xử lý resolve foreign key labels cho result rows.
"""
from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa

from core.database import engine


def _load_lookup_relations() -> list[dict]:
    path = Path("db.json")
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[dict] = []
    for rel in (raw.get("relations", {}).get("lookup", []) or []):
        if not isinstance(rel, dict):
            continue
        from_table = str(rel.get("from_table", "")).strip()
        from_field = str(rel.get("from_field", "")).strip()
        to_table = str(rel.get("to_table", "")).strip()
        to_field = str(rel.get("to_field", "")).strip()
        if from_table and from_field and to_table and to_field:
            out.append(
                {
                    "from_table": from_table,
                    "from_field": from_field,
                    "to_table": to_table,
                    "to_field": to_field,
                }
            )
    return out


def _is_uuid_like(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if len(text) != 36:
        return False
    chunks = text.split("-")
    if [len(c) for c in chunks] != [8, 4, 4, 4, 12]:
        return False
    hex_digits = set("0123456789abcdefABCDEF")
    return all(all(ch in hex_digits for ch in chunk) for chunk in chunks)


def _guess_label_column(table_name: str) -> str | None:
    try:
        table = sa.Table(table_name, sa.MetaData(), autoload_with=engine)
    except Exception:
        return None
    candidates: list[str] = []
    for col in table.columns.keys():
        c = str(col)
        lc = c.lower()
        if lc.endswith("_name") or lc.endswith("name"):
            candidates.append(c)
        elif "fullname" in lc or "full_name" in lc:
            candidates.append(c)
        elif lc in {"name", "fullname", "full_name"}:
            candidates.append(c)
    if candidates:
        candidates.sort(key=lambda x: (0 if "name" in x.lower() else 1, len(x)))
        return candidates[0]
    return None


def resolve_fk_labels(root_table: str, rows: list[dict]) -> list[dict]:
    """Enrich result rows với FK label columns từ lookup relations trong db.json."""
    relations = _load_lookup_relations()
    rel_map: dict[str, dict] = {}
    for rel in relations:
        if rel.get("from_table") == root_table:
            rel_map[str(rel.get("from_field"))] = rel
    if not rel_map or not rows:
        return rows

    resolved_rows: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            resolved_rows.append(row)
            continue
        decorated = dict(row)
        for fk_field, rel in rel_map.items():
            fk_value = row.get(fk_field)
            if fk_value in (None, ""):
                continue
            target_table = str(rel.get("to_table"))
            target_pk = str(rel.get("to_field"))
            label_col = _guess_label_column(target_table)
            if not label_col:
                continue
            try:
                t = sa.Table(target_table, sa.MetaData(), autoload_with=engine)
                stmt = sa.select(t.c[label_col]).where(t.c[target_pk] == fk_value).limit(1)
                with engine.connect() as conn:
                    label = conn.execute(stmt).scalar_one_or_none()
                if label not in (None, ""):
                    decorated[f"{fk_field}_label"] = label
            except Exception:
                continue
        resolved_rows.append(decorated)
    return resolved_rows


# Alias cho backwards compat với service.py cũ
_resolve_fk_labels = resolve_fk_labels
