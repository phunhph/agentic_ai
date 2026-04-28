import argparse
import json
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa

# Ensure project root is importable when running as a direct script.
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from storage.database import engine


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _sql_type(type_name: str) -> str:
    t = str(type_name or "").strip().lower()
    mapping = {
        "uuid": "UUID",
        "datetime": "TIMESTAMP WITH TIME ZONE",
        "text": "TEXT",
        "richtext": "TEXT",
        "int": "INTEGER",
        "decimal": "NUMERIC",
        "bool": "BOOLEAN",
    }
    return mapping.get(t, "TEXT")


def _table_exists(conn: sa.Connection, table_name: str) -> bool:
    stmt = sa.text(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = 'public' AND table_name = :table_name
        ) AS ok
        """
    )
    return bool(conn.execute(stmt, {"table_name": table_name}).scalar())


def _columns_for_table(conn: sa.Connection, table_name: str) -> set[str]:
    stmt = sa.text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        """
    )
    rows = conn.execute(stmt, {"table_name": table_name}).fetchall()
    return {str(r[0]) for r in rows}


def _ensure_table(conn: sa.Connection, table: dict[str, Any]) -> dict[str, int]:
    table_name = str(table["name"])
    fields = [f for f in table.get("fields", []) if isinstance(f, dict) and str(f.get("name", "")).strip()]
    if not fields:
        return {"created_tables": 0, "added_columns": 0}

    created_tables = 0
    added_columns = 0
    pk = str(table.get("primary_key", "")).strip()

    if not _table_exists(conn, table_name):
        col_defs: list[str] = []
        for f in fields:
            col_name = str(f["name"])
            col_type = _sql_type(str(f.get("type", "text")))
            nullable = bool(f.get("nullable", True))
            null_sql = "NULL" if nullable else "NOT NULL"
            col_defs.append(f"{_quote_ident(col_name)} {col_type} {null_sql}")
        if pk:
            col_defs.append(f"PRIMARY KEY ({_quote_ident(pk)})")
        create_sql = f"CREATE TABLE {_quote_ident(table_name)} ({', '.join(col_defs)})"
        conn.execute(sa.text(create_sql))
        created_tables = 1
        return {"created_tables": created_tables, "added_columns": added_columns}

    existing_cols = _columns_for_table(conn, table_name)
    for f in fields:
        col_name = str(f["name"])
        if col_name in existing_cols:
            continue
        col_type = _sql_type(str(f.get("type", "text")))
        # For existing tables, add new columns as NULLABLE first to avoid
        # failing when historical rows exist without values for that column.
        null_sql = "NULL"
        alter_sql = f"ALTER TABLE {_quote_ident(table_name)} ADD COLUMN {_quote_ident(col_name)} {col_type} {null_sql}"
        conn.execute(sa.text(alter_sql))
        added_columns += 1

    # Ensure PK exists when table pre-exists and pk is available.
    if pk and pk in {str(f.get('name')) for f in fields}:
        pk_stmt = sa.text(
            """
            SELECT COUNT(*) FROM information_schema.table_constraints
            WHERE table_schema='public' AND table_name=:table_name AND constraint_type='PRIMARY KEY'
            """
        )
        has_pk = int(conn.execute(pk_stmt, {"table_name": table_name}).scalar() or 0) > 0
        if not has_pk:
            alter_pk = (
                f"ALTER TABLE {_quote_ident(table_name)} "
                f"ADD CONSTRAINT {_quote_ident(table_name + '_pkey')} PRIMARY KEY ({_quote_ident(pk)})"
            )
            conn.execute(sa.text(alter_pk))

    return {"created_tables": created_tables, "added_columns": added_columns}


def _upsert_rows(
    conn: sa.Connection,
    table: dict[str, Any],
    staging_dir: Path,
    replace_existing_data: bool = False,
) -> int:
    table_name = str(table["name"])
    pk = str(table.get("primary_key", "")).strip()
    if not pk:
        return 0

    data_path = staging_dir / f"{table_name}.jsonl"
    if not data_path.exists():
        return 0

    raw_lines = [x for x in data_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not raw_lines:
        return 0

    rows: list[dict[str, Any]] = []
    for ln in raw_lines:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    if not rows:
        return 0

    # Align to current DB columns only.
    valid_cols = _columns_for_table(conn, table_name)
    cleaned_rows: list[dict[str, Any]] = []
    for row in rows:
        if pk not in row or row.get(pk) in (None, ""):
            continue
        cleaned = {k: v for k, v in row.items() if k in valid_cols}
        if pk in cleaned:
            cleaned_rows.append(cleaned)
    if not cleaned_rows:
        return 0

    all_cols = sorted({k for r in cleaned_rows for k in r.keys()})
    if pk not in all_cols:
        return 0

    col_sql = ", ".join(_quote_ident(c) for c in all_cols)
    value_sql = ", ".join(f":{c}" for c in all_cols)
    update_cols = [c for c in all_cols if c != pk]
    if update_cols:
        update_sql = ", ".join(f"{_quote_ident(c)} = EXCLUDED.{_quote_ident(c)}" for c in update_cols)
        sql = (
            f"INSERT INTO {_quote_ident(table_name)} ({col_sql}) VALUES ({value_sql}) "
            f"ON CONFLICT ({_quote_ident(pk)}) DO UPDATE SET {update_sql}"
        )
    else:
        sql = (
            f"INSERT INTO {_quote_ident(table_name)} ({col_sql}) VALUES ({value_sql}) "
            f"ON CONFLICT ({_quote_ident(pk)}) DO NOTHING"
        )
    conn.execute(sa.text(sql), cleaned_rows)
    return len(cleaned_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize V3 staging data into V2 runtime database")
    parser.add_argument("--db-json", default="db.json")
    parser.add_argument("--staging-dir", default="v3/storage/dataverse_data_staging")
    parser.add_argument("--tables", default="", help="Comma-separated logical table names")
    parser.add_argument(
        "--replace-existing-data",
        action="store_true",
        help="If set, truncate selected tables before loading staged data.",
    )
    args = parser.parse_args()

    db_json = _read_json(Path(args.db_json))
    all_tables = [t for t in db_json.get("tables", []) if isinstance(t, dict) and str(t.get("name", "")).strip()]
    if args.tables:
        selected = {x.strip() for x in str(args.tables).split(",") if x.strip()}
        all_tables = [t for t in all_tables if str(t.get("name", "")) in selected]

    staging_dir = Path(args.staging_dir)
    stats = {
        "tables_total": len(all_tables),
        "created_tables": 0,
        "added_columns": 0,
        "upserted_rows": 0,
        "details": [],
    }

    with engine.begin() as conn:
        if bool(args.replace_existing_data) and all_tables:
            truncate_targets = ", ".join(_quote_ident(str(t["name"])) for t in all_tables)
            conn.execute(sa.text(f"TRUNCATE TABLE {truncate_targets} RESTART IDENTITY CASCADE"))
        for table in all_tables:
            tname = str(table["name"])
            schema_stat = _ensure_table(conn, table)
            upserted = _upsert_rows(
                conn,
                table,
                staging_dir,
                replace_existing_data=bool(args.replace_existing_data),
            )
            stats["created_tables"] += int(schema_stat["created_tables"])
            stats["added_columns"] += int(schema_stat["added_columns"])
            stats["upserted_rows"] += int(upserted)
            stats["details"].append(
                {
                    "table": tname,
                    "created_table": bool(schema_stat["created_tables"]),
                    "added_columns": int(schema_stat["added_columns"]),
                    "upserted_rows": int(upserted),
                }
            )

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
