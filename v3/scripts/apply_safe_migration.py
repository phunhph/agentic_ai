import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply safe migration operations from plan")
    parser.add_argument(
        "--migration-plan",
        default="v3/storage/dataverse_migration_plans/latest_migration_plan.json",
    )
    parser.add_argument(
        "--applied-log",
        default="v3/storage/dataverse_migration_plans/latest_applied_safe_migrations.json",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="If enabled, mark safe ops as applied. Otherwise dry-run preview.",
    )
    args = parser.parse_args()

    plan = _read_json(Path(args.migration_plan))
    ops = plan.get("operations", [])
    safe_ops = [op for op in ops if op.get("safe_auto_apply")]
    manual_ops = [op for op in ops if not op.get("safe_auto_apply")]

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "migration_plan": args.migration_plan,
        "dry_run": not args.execute,
        "safe_operation_count": len(safe_ops),
        "manual_operation_count": len(manual_ops),
        "applied_operations": safe_ops if args.execute else [],
        "pending_manual_operations": manual_ops,
    }

    out = Path(args.applied_log)
    _write_json(out, result)
    print(f"Wrote safe migration report to {out}")
    print(json.dumps(
        {
            "dry_run": result["dry_run"],
            "safe_operation_count": result["safe_operation_count"],
            "manual_operation_count": result["manual_operation_count"],
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
