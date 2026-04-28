import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dataverse_client import DataverseClient, DataverseConfig, _build_config_from_env

CHOICE_TYPES = {"Picklist", "MultiSelectPicklist", "State", "Status", "Boolean"}


def _load_schema_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_checkpoint(path: Path) -> dict[str, Any]:
    return _read_json(path)


def _write_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    _write_json(path, checkpoint)


def _table_columns(table: dict[str, Any]) -> list[str]:
    raw_fields = table.get("fields", [])
    names: list[str] = []
    readable_names: set[str] = set()
    for f in raw_fields:
        name = str(f.get("name", "")).strip()
        if not name:
            continue
        is_valid_for_read = f.get("is_valid_for_read")
        if is_valid_for_read is False:
            continue
        names.append(name)
        readable_names.add(name)

    # Avoid common formatted companion properties that often fail in $select,
    # e.g. lookupname / lookupyominame not exposed as real columns.
    filtered: list[str] = []
    for name in names:
        if name.endswith("yominame"):
            base = name[: -len("yominame")]
            if base in readable_names:
                continue
        if name.endswith("name"):
            base = name[: -len("name")]
            if base in readable_names:
                continue
        filtered.append(name)

    # Keep order, remove duplicates
    return list(dict.fromkeys(filtered))


def _build_incremental_filter(checkpoint_value: str) -> str:
    # Dataverse/OData is more reliable with UTC Z format in query filters.
    raw = str(checkpoint_value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return f"modifiedon ge {raw}"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    # Keep second precision to avoid parsing issues in some Dataverse orgs.
    safe_value = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"modifiedon ge {safe_value}"


def _run_table_sync(
    client: DataverseClient,
    table: dict[str, Any],
    output_dir: Path,
    mode: str,
    checkpoint_value: str,
) -> dict[str, Any]:
    tname = str(table["name"])
    entity_set_name = str(table.get("entity_set_name", ""))
    if not entity_set_name:
        return {"table": tname, "skipped": True, "reason": "missing_entity_set_name"}

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{tname}.jsonl"
    total = 0
    next_link = ""
    filter_clause = ""
    if mode == "incremental" and checkpoint_value:
        filter_clause = _build_incremental_filter(checkpoint_value)

    field_types: dict[str, str] = {}
    for f in table.get("fields", []):
        if not isinstance(f, dict):
            continue
        fname = str(f.get("name", "")).strip()
        if not fname:
            continue
        field_types[fname] = str(f.get("attribute_type", "")).strip()

    file_mode = "a" if mode == "incremental" else "w"
    with out_file.open(file_mode, encoding="utf-8") as fh:
        while True:
            page = client.fetch_records_page(
                entity_set_name=entity_set_name,
                select_columns=_table_columns(table),
                filter_clause=filter_clause,
                order_by="modifiedon asc",
                top=500,
                next_link=next_link,
            )
            values = page.get("value", [])
            for row in values:
                normalized = _normalize_dataverse_row(row, field_types)
                fh.write(json.dumps(normalized, ensure_ascii=True) + "\n")
            total += len(values)
            next_link = page.get("@odata.nextLink", "")
            if not next_link:
                break

    return {
        "table": tname,
        "output_file": str(out_file),
        "fetched": total,
        "write_mode": file_mode,
    }


def _normalize_dataverse_row(row: dict[str, Any], field_types: dict[str, str]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    out: dict[str, Any] = {}
    # 1) Keep normal properties.
    for k, v in row.items():
        key = str(k)
        if "@OData.Community.Display.V1.FormattedValue" in key:
            continue
        if key.startswith("@"):
            continue
        out[key] = v

    # 2) Flatten formatted labels into <field>_label.
    suffix = "@OData.Community.Display.V1.FormattedValue"
    for k, v in row.items():
        key = str(k)
        if not key.endswith(suffix):
            continue
        base = key[: -len(suffix)]
        if not base:
            continue
        label_key = f"{base}_label"
        out[label_key] = v

    # 3) Normalize choice fields to a stable shape.
    # - Single choice: still expose <field>_choices as list of one.
    # - Multi choice: expose list with 1..n values.
    for fname, attr_type in field_types.items():
        if attr_type not in CHOICE_TYPES:
            continue
        raw_value = out.get(fname)
        raw_label = out.get(f"{fname}_label")
        is_multi = attr_type == "MultiSelectPicklist"

        values: list[Any]
        labels: list[str]
        if is_multi:
            if isinstance(raw_value, list):
                values = raw_value
            elif isinstance(raw_value, str):
                values = [x.strip() for x in raw_value.split(",") if x.strip()]
            elif raw_value in (None, ""):
                values = []
            else:
                values = [raw_value]
            if isinstance(raw_label, str):
                labels = [x.strip() for x in raw_label.split(";") if x.strip()]
            else:
                labels = []
        else:
            values = [] if raw_value in (None, "") else [raw_value]
            labels = [str(raw_label)] if raw_label not in (None, "") else []

        choices: list[dict[str, Any]] = []
        for idx, value in enumerate(values):
            label = labels[idx] if idx < len(labels) else (labels[0] if labels and not is_multi else None)
            choices.append({"value": value, "label": label})

        out[f"{fname}_is_multi"] = is_multi
        out[f"{fname}_choices"] = choices
        if not is_multi:
            out[f"{fname}_choice"] = choices[0] if choices else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Dataverse records into local jsonl staging")
    parser.add_argument(
        "--schema-snapshot",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
    )
    parser.add_argument(
        "--output-dir",
        default="v3/storage/dataverse_data_staging",
    )
    parser.add_argument(
        "--checkpoint-file",
        default="v3/storage/dataverse_checkpoints.json",
    )
    parser.add_argument("--table-limit", type=int, default=0)
    parser.add_argument("--tables", default="", help="Comma-separated logical table names")
    args = parser.parse_args()

    snapshot = _load_schema_snapshot(Path(args.schema_snapshot))
    tables = snapshot.get("tables", [])
    if args.tables:
        include_tables = {x.strip() for x in str(args.tables).split(",") if x.strip()}
        tables = [t for t in tables if str(t.get("name", "")) in include_tables]
    if args.table_limit > 0:
        tables = tables[: args.table_limit]

    config: DataverseConfig = _build_config_from_env()
    client = DataverseClient(config)
    client.get_access_token()

    checkpoint_file = Path(args.checkpoint_file)
    checkpoint = _read_checkpoint(checkpoint_file)
    default_cp = str(checkpoint.get("last_modifiedon", ""))
    run_summary: list[dict[str, Any]] = []

    for table in tables:
        table_cp = str(checkpoint.get("tables", {}).get(table.get("name", ""), default_cp))
        summary = _run_table_sync(
            client=client,
            table=table,
            output_dir=Path(args.output_dir),
            mode=args.mode,
            checkpoint_value=table_cp,
        )
        run_summary.append(summary)

    checkpoint.setdefault("tables", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    checkpoint["last_modifiedon"] = now_iso
    for item in run_summary:
        if item.get("table") and (not item.get("skipped")):
            checkpoint["tables"][item["table"]] = now_iso
    _write_checkpoint(checkpoint_file, checkpoint)

    result = {
        "mode": args.mode,
        "synced_tables": len([x for x in run_summary if not x.get("skipped")]),
        "skipped_tables": len([x for x in run_summary if x.get("skipped")]),
        "details": run_summary,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
