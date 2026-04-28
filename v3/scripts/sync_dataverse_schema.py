import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dataverse_client import DataverseClient, _build_config_from_env


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Dataverse schema snapshot")
    parser.add_argument("--table-prefix", default="")
    parser.add_argument("--tables", default="", help="Comma-separated logical table names")
    parser.add_argument("--table-limit", type=int, default=0, help="0 means no limit")
    parser.add_argument(
        "--output",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    args = parser.parse_args()

    client = DataverseClient(_build_config_from_env())
    client.get_access_token()
    include_tables: set[str] | None = None
    if args.tables:
        include_tables = {x.strip() for x in str(args.tables).split(",") if x.strip()}
    tables = client.list_tables_metadata(table_prefix=args.table_prefix, include_tables=include_tables)
    if args.table_limit > 0:
        tables = tables[: args.table_limit]

    for table in tables:
        table["fields"] = client.list_table_columns(table["name"])

    payload = {
        "source": "dataverse",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "table_count": len(tables),
        "tables": tables,
    }
    out = Path(args.output)
    _write_json(out, payload)
    print(f"Schema synced to {out}")
    print(json.dumps({"table_count": len(tables)}, indent=2))


if __name__ == "__main__":
    main()
