import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_step(name: str, cmd: list[str]) -> None:
    print(f"[BOOTSTRAP] {name}")
    print(f"[BOOTSTRAP] CMD: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {name} (exit={result.returncode})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Dataverse bootstrap flow: sync_schema -> diff -> migration_plan -> apply_safe_migration -> optional db.json update"
    )
    parser.add_argument("--table-prefix", default="")
    parser.add_argument("--tables", default="", help="Comma-separated logical table names")
    parser.add_argument("--table-limit", type=int, default=0)
    parser.add_argument(
        "--schema-snapshot",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    parser.add_argument(
        "--schema-diff",
        default="v3/storage/dataverse_migration_plans/latest_schema_diff.json",
    )
    parser.add_argument(
        "--migration-plan",
        default="v3/storage/dataverse_migration_plans/latest_migration_plan.json",
    )
    parser.add_argument(
        "--applied-safe-log",
        default="v3/storage/dataverse_migration_plans/latest_applied_safe_migrations.json",
    )
    parser.add_argument("--db-json", default="db.json")
    parser.add_argument("--backup-dir", default="v3/storage/dataverse_schema_snapshots")
    parser.add_argument(
        "--update-db-json",
        action="store_true",
        help="If set, apply baseline update into db.json (otherwise dry-run only).",
    )
    args = parser.parse_args()

    schema_sync_cmd = [
        sys.executable,
        "v3/scripts/sync_dataverse_schema.py",
        "--output",
        args.schema_snapshot,
    ]
    if args.table_prefix:
        schema_sync_cmd += ["--table-prefix", args.table_prefix]
    if args.tables:
        schema_sync_cmd += ["--tables", args.tables]
    if args.table_limit > 0:
        schema_sync_cmd += ["--table-limit", str(args.table_limit)]

    _run_step("Sync schema snapshot", schema_sync_cmd)

    _run_step(
        "Generate schema diff",
        [
            sys.executable,
            "v3/scripts/dataverse_schema_diff.py",
            "--db-json",
            args.db_json,
            "--schema-snapshot",
            args.schema_snapshot,
            "--output",
            args.schema_diff,
        ],
    )

    _run_step(
        "Generate migration plan",
        [
            sys.executable,
            "v3/scripts/dataverse_migration_planner.py",
            "--schema-diff",
            args.schema_diff,
            "--output",
            args.migration_plan,
        ],
    )

    safe_cmd = [
        sys.executable,
        "v3/scripts/apply_safe_migration.py",
        "--migration-plan",
        args.migration_plan,
        "--applied-log",
        args.applied_safe_log,
    ]
    if args.update_db_json:
        safe_cmd.append("--execute")
    _run_step("Apply safe migrations", safe_cmd)

    update_cmd = [
        sys.executable,
        "v3/scripts/update_db_json_baseline.py",
        "--db-json",
        args.db_json,
        "--schema-snapshot",
        args.schema_snapshot,
        "--backup-dir",
        args.backup_dir,
    ]
    if not args.update_db_json:
        update_cmd.append("--dry-run")
    _run_step("Update db.json baseline", update_cmd)

    print("[BOOTSTRAP] Completed successfully.")
    if not args.update_db_json:
        print("[BOOTSTRAP] Note: db.json was not changed (dry-run).")
        print("[BOOTSTRAP] Re-run with --update-db-json to write changes.")


if __name__ == "__main__":
    main()
