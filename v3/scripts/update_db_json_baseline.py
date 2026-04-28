import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _map_attr_type(attr_type: str) -> str:
    mapping = {
        "Uniqueidentifier": "uuid",
        "DateTime": "datetime",
        "String": "text",
        "Memo": "richtext",
        "Integer": "int",
        "BigInt": "int",
        "Decimal": "decimal",
        "Double": "decimal",
        "Money": "decimal",
        "Boolean": "bool",
        "Lookup": "uuid",
        "Owner": "uuid",
        "Picklist": "text",
        "State": "text",
        "Status": "text",
    }
    return mapping.get(attr_type, "text")


def _to_db_json_table(raw: dict[str, Any]) -> dict[str, Any]:
    fields = []
    for f in raw.get("fields", []):
        fname = str(f.get("name", "")).strip()
        if not fname:
            continue
        required_level = str(f.get("required_level", "")).lower()
        nullable = required_level not in {"systemrequired", "applicationrequired"}
        fields.append(
            {
                "name": fname,
                "type": _map_attr_type(str(f.get("attribute_type", ""))),
                "nullable": nullable,
            }
        )

    return {
        "name": raw.get("name"),
        "primary_key": raw.get("primary_key"),
        "fields": sorted(fields, key=lambda x: x["name"]),
    }


def update_baseline(db_json: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    current_tables = {
        str(t.get("name", "")): t
        for t in db_json.get("tables", [])
        if str(t.get("name", ""))
    }
    for snap_table in snapshot.get("tables", []):
        t = _to_db_json_table(snap_table)
        tname = str(t.get("name", ""))
        if not tname:
            continue
        current_tables[tname] = t

    db_json["tables"] = sorted(current_tables.values(), key=lambda x: str(x.get("name", "")))
    db_json["version"] = int(db_json.get("version", 0)) + 1
    meta = db_json.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    meta["last_schema_sync_at"] = datetime.now(timezone.utc).isoformat()
    meta["schema_source"] = "dataverse_snapshot"
    db_json["meta"] = meta
    return db_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Update db.json baseline using Dataverse schema snapshot")
    parser.add_argument("--db-json", default="db.json")
    parser.add_argument(
        "--schema-snapshot",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    parser.add_argument("--backup-dir", default="v3/storage/dataverse_schema_snapshots")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db_json)
    snapshot_path = Path(args.schema_snapshot)
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_json = _read_json(db_path)
    snapshot = _read_json(snapshot_path)
    updated = update_baseline(db_json, snapshot)

    if args.dry_run:
        print("Dry run mode. db.json not updated.")
        print(f"Projected table count: {len(updated.get('tables', []))}")
        print(f"Projected version: {updated.get('version')}")
        return

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"db.json.backup.{ts}.json"
    backup_path.write_text(json.dumps(db_json, indent=2), encoding="utf-8")
    db_path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    print(f"Updated {db_path}")
    print(f"Backup saved at {backup_path}")


if __name__ == "__main__":
    main()
