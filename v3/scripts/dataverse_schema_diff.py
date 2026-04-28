import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_db_json(db_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tables = db_json.get("tables", [])
    out: dict[str, dict[str, Any]] = {}
    for table in tables:
        tname = str(table.get("name", ""))
        if not tname:
            continue
        fields = table.get("fields", [])
        out[tname] = {
            "name": tname,
            "primary_key": table.get("primary_key"),
            "fields": {
                str(f.get("name", "")): {
                    "name": str(f.get("name", "")),
                    "type": str(f.get("type", "text")),
                    "nullable": bool(f.get("nullable", True)),
                }
                for f in fields
                if str(f.get("name", ""))
            },
        }
    return out


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


def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for table in snapshot.get("tables", []):
        tname = str(table.get("name", ""))
        if not tname:
            continue
        fields: dict[str, Any] = {}
        for raw in table.get("fields", []):
            fname = str(raw.get("name", ""))
            if not fname:
                continue
            required_level = str(raw.get("required_level", "")).lower()
            nullable = required_level not in {"systemrequired", "applicationrequired"}
            fields[fname] = {
                "name": fname,
                "type": _map_attr_type(str(raw.get("attribute_type", ""))),
                "nullable": nullable,
            }
        out[tname] = {
            "name": tname,
            "primary_key": table.get("primary_key"),
            "fields": fields,
        }
    return out


def _sorted_names(d: dict[str, Any]) -> list[str]:
    return sorted(d.keys())


def build_diff(db_json: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    base = _normalize_db_json(db_json)
    incoming = _normalize_snapshot(snapshot)

    base_tables = set(base.keys())
    incoming_tables = set(incoming.keys())

    new_tables = sorted(incoming_tables - base_tables)
    removed_tables = sorted(base_tables - incoming_tables)
    common_tables = sorted(base_tables & incoming_tables)

    table_diffs: list[dict[str, Any]] = []
    for tname in common_tables:
        left = base[tname]
        right = incoming[tname]
        left_fields = left["fields"]
        right_fields = right["fields"]

        added_fields = _sorted_names({k: v for k, v in right_fields.items() if k not in left_fields})
        removed_fields = _sorted_names({k: v for k, v in left_fields.items() if k not in right_fields})

        changed_fields: list[dict[str, Any]] = []
        for fname in sorted(set(left_fields.keys()) & set(right_fields.keys())):
            lf = left_fields[fname]
            rf = right_fields[fname]
            if lf["type"] != rf["type"] or lf["nullable"] != rf["nullable"]:
                changed_fields.append(
                    {
                        "field": fname,
                        "before": lf,
                        "after": rf,
                    }
                )

        pk_changed = left.get("primary_key") != right.get("primary_key")
        if added_fields or removed_fields or changed_fields or pk_changed:
            table_diffs.append(
                {
                    "table": tname,
                    "primary_key_before": left.get("primary_key"),
                    "primary_key_after": right.get("primary_key"),
                    "primary_key_changed": pk_changed,
                    "added_fields": added_fields,
                    "removed_fields": removed_fields,
                    "changed_fields": changed_fields,
                }
            )

    return {
        "summary": {
            "new_tables": len(new_tables),
            "removed_tables": len(removed_tables),
            "changed_tables": len(table_diffs),
        },
        "new_tables": [incoming[t] for t in new_tables],
        "removed_tables": [base[t] for t in removed_tables],
        "changed_tables": table_diffs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diff Dataverse schema snapshot against db.json")
    parser.add_argument("--db-json", default="db.json")
    parser.add_argument(
        "--schema-snapshot",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    parser.add_argument(
        "--output",
        default="v3/storage/dataverse_migration_plans/latest_schema_diff.json",
    )
    args = parser.parse_args()

    db_json = _read_json(Path(args.db_json))
    snapshot = _read_json(Path(args.schema_snapshot))
    diff = build_diff(db_json, snapshot)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(diff, indent=2), encoding="utf-8")
    print(f"Wrote schema diff to {out}")
    print(json.dumps(diff["summary"], indent=2))


if __name__ == "__main__":
    main()
