import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _is_choice_type(attr_type: str) -> bool:
    return attr_type in {"Picklist", "MultiSelectPicklist", "State", "Status", "Boolean"}


def _collect_choice_options(schema_snapshot: dict[str, Any], staging_dir: Path) -> dict[str, list[dict[str, str]]]:
    collected: dict[str, dict[str, str]] = {}
    for table in schema_snapshot.get("tables", []):
        if not isinstance(table, dict):
            continue
        tname = str(table.get("name", "")).strip()
        if not tname:
            continue
        rows = _read_jsonl(staging_dir / f"{tname}.jsonl")
        if not rows:
            continue

        choice_fields = [
            str(f.get("name", "")).strip()
            for f in table.get("fields", [])
            if isinstance(f, dict) and _is_choice_type(str(f.get("attribute_type", "")))
        ]
        for fname in choice_fields:
            key = f"{tname}.{fname}"
            bucket = collected.setdefault(key, {})
            for row in rows:
                choices = row.get(f"{fname}_choices")
                if isinstance(choices, list) and choices:
                    for ch in choices:
                        if not isinstance(ch, dict):
                            continue
                        value = ch.get("value")
                        label = ch.get("label")
                        if value in (None, ""):
                            continue
                        code = str(value)
                        text = str(label) if label not in (None, "") else code
                        bucket[code] = text
                    continue

                value = row.get(fname)
                if value in (None, ""):
                    continue
                label = row.get(f"{fname}_label")
                code = str(value)
                text = str(label) if label not in (None, "") else code
                bucket[code] = text

    out: dict[str, list[dict[str, str]]] = {}
    for key, kv in collected.items():
        out[key] = [{"code": code, "label": kv[code]} for code in sorted(kv.keys())]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Update db.json choice_options from staging data")
    parser.add_argument("--db-json", default="db.json")
    parser.add_argument(
        "--schema-snapshot",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    parser.add_argument("--staging-dir", default="v3/storage/dataverse_data_staging")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db_json)
    db_json = _read_json(db_path)
    schema = _read_json(Path(args.schema_snapshot))
    choices = _collect_choice_options(schema, Path(args.staging_dir))

    if args.backup:
        backup_path = db_path.with_suffix(".choice_backup.json")
        backup_path.write_text(json.dumps(db_json, indent=2), encoding="utf-8")
        print(f"Backup saved: {backup_path}")

    db_json["choice_options"] = choices
    meta = db_json.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    meta["choice_options_source"] = "staging_runtime_data"
    db_json["meta"] = meta
    db_path.write_text(json.dumps(db_json, indent=2), encoding="utf-8")
    print(f"Updated {db_path} with {len(choices)} choice groups")


if __name__ == "__main__":
    main()
