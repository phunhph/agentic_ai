import argparse
import json
from pathlib import Path
from typing import Any


CHOICE_TYPES = {"Picklist", "MultiSelectPicklist", "State", "Status", "Boolean"}


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


def _is_non_empty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Dataverse choice fields and label coverage")
    parser.add_argument(
        "--schema-snapshot",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    parser.add_argument(
        "--staging-dir",
        default="v3/storage/dataverse_data_staging",
    )
    parser.add_argument("--tables", default="", help="Comma-separated table names")
    parser.add_argument(
        "--output",
        default="v3/storage/dataverse_migration_plans/choice_quality_report.json",
    )
    args = parser.parse_args()

    snapshot = _read_json(Path(args.schema_snapshot))
    tables = [t for t in snapshot.get("tables", []) if isinstance(t, dict)]
    if args.tables:
        wanted = {x.strip() for x in str(args.tables).split(",") if x.strip()}
        tables = [t for t in tables if str(t.get("name", "")) in wanted]

    report_tables: list[dict[str, Any]] = []
    summary = {
        "tables_scanned": 0,
        "choice_fields_total": 0,
        "multi_choice_fields": 0,
        "fields_missing_label_coverage": 0,
    }
    staging_dir = Path(args.staging_dir)

    for table in tables:
        tname = str(table.get("name", ""))
        if not tname:
            continue
        rows = _read_jsonl(staging_dir / f"{tname}.jsonl")
        choice_fields: list[dict[str, Any]] = []
        for field in table.get("fields", []):
            if not isinstance(field, dict):
                continue
            attr_type = str(field.get("attribute_type", ""))
            if attr_type not in CHOICE_TYPES:
                continue
            fname = str(field.get("name", ""))
            if not fname:
                continue
            label_key = f"{fname}_label"
            value_count = 0
            labeled_count = 0
            for row in rows:
                if _is_non_empty(row.get(fname)):
                    value_count += 1
                    if _is_non_empty(row.get(label_key)):
                        labeled_count += 1
            coverage = 1.0 if value_count == 0 else (labeled_count / value_count)
            choice_fields.append(
                {
                    "field": fname,
                    "attribute_type": attr_type,
                    "is_multi": attr_type == "MultiSelectPicklist",
                    "records_with_value": value_count,
                    "records_with_label": labeled_count,
                    "label_coverage": round(coverage, 4),
                }
            )

        if not choice_fields:
            continue
        summary["tables_scanned"] += 1
        summary["choice_fields_total"] += len(choice_fields)
        summary["multi_choice_fields"] += len([f for f in choice_fields if f["is_multi"]])
        summary["fields_missing_label_coverage"] += len([f for f in choice_fields if f["label_coverage"] < 1.0])
        report_tables.append(
            {
                "table": tname,
                "rows_in_staging": len(rows),
                "choice_fields": choice_fields,
            }
        )

    payload = {"summary": summary, "tables": report_tables}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote choice quality report to {out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
