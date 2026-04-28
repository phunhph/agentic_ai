import argparse
import json
from pathlib import Path
from typing import Any


SAFE_OPS = {"create_table", "add_column"}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _sql_type(t: str) -> str:
    m = {
        "uuid": "UUID",
        "text": "TEXT",
        "richtext": "TEXT",
        "datetime": "TIMESTAMP",
        "int": "INTEGER",
        "decimal": "NUMERIC",
        "bool": "BOOLEAN",
    }
    return m.get(t, "TEXT")


def _safe_flag(op_type: str) -> bool:
    return op_type in SAFE_OPS


def build_plan(diff: dict[str, Any]) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []

    for table in diff.get("new_tables", []):
        tname = table["name"]
        operations.append(
            {
                "operation": "create_table",
                "safe_auto_apply": True,
                "table": tname,
                "details": {"primary_key": table.get("primary_key"), "fields": list(table.get("fields", {}).values())},
                "sql_hint": f"-- create table {tname} with mapped columns",
            }
        )

    for table in diff.get("removed_tables", []):
        operations.append(
            {
                "operation": "drop_table",
                "safe_auto_apply": False,
                "table": table["name"],
                "details": {},
                "sql_hint": f"DROP TABLE IF EXISTS {table['name']};",
            }
        )

    for changed in diff.get("changed_tables", []):
        tname = changed["table"]
        if changed.get("primary_key_changed"):
            operations.append(
                {
                    "operation": "change_primary_key",
                    "safe_auto_apply": False,
                    "table": tname,
                    "details": {
                        "before": changed.get("primary_key_before"),
                        "after": changed.get("primary_key_after"),
                    },
                    "sql_hint": f"-- manual: alter primary key for {tname}",
                }
            )

        for fname in changed.get("added_fields", []):
            operations.append(
                {
                    "operation": "add_column",
                    "safe_auto_apply": True,
                    "table": tname,
                    "details": {"field": fname},
                    "sql_hint": f"ALTER TABLE {tname} ADD COLUMN {fname} TEXT NULL;",
                }
            )

        for fname in changed.get("removed_fields", []):
            operations.append(
                {
                    "operation": "drop_column",
                    "safe_auto_apply": False,
                    "table": tname,
                    "details": {"field": fname},
                    "sql_hint": f"ALTER TABLE {tname} DROP COLUMN {fname};",
                }
            )

        for c in changed.get("changed_fields", []):
            before = c.get("before", {})
            after = c.get("after", {})
            op_type = "alter_column_type" if before.get("type") != after.get("type") else "alter_column_nullable"
            safe = False
            sql_hint = f"-- manual: alter {tname}.{c['field']} from {before} to {after}"
            if op_type == "alter_column_nullable" and before.get("nullable") and (not after.get("nullable")):
                safe = False
            operations.append(
                {
                    "operation": op_type,
                    "safe_auto_apply": safe,
                    "table": tname,
                    "details": c,
                    "sql_hint": sql_hint,
                }
            )

    safe_ops = [op for op in operations if op["safe_auto_apply"]]
    manual_ops = [op for op in operations if not op["safe_auto_apply"]]

    return {
        "summary": {
            "total_operations": len(operations),
            "safe_operations": len(safe_ops),
            "manual_operations": len(manual_ops),
        },
        "operations": operations,
        "safe_operation_types": sorted({op["operation"] for op in operations if _safe_flag(op["operation"])}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build migration plan from schema diff")
    parser.add_argument(
        "--schema-diff",
        default="v3/storage/dataverse_migration_plans/latest_schema_diff.json",
    )
    parser.add_argument(
        "--output",
        default="v3/storage/dataverse_migration_plans/latest_migration_plan.json",
    )
    args = parser.parse_args()

    diff = _read_json(Path(args.schema_diff))
    plan = build_plan(diff)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Wrote migration plan to {out}")
    print(json.dumps(plan["summary"], indent=2))


if __name__ == "__main__":
    main()
