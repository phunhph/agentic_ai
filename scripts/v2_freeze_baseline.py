from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

BASELINE_FILES = [
    "storage/dynamic_cases.json",
    "storage/dynamic_eval_report.json",
    "storage/learning/learning_data.json",
    "storage/learning/learning_data_default_inventory.json",
    "storage/learning/learning_data_default_sales.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    snapshot_root = Path("storage/v2/snapshots") / ts
    snapshot_root.mkdir(parents=True, exist_ok=True)

    snapshot_manifest: dict[str, dict[str, str | int]] = {}
    for raw in BASELINE_FILES:
        src = Path(raw)
        if not src.exists():
            continue
        dst = snapshot_root / src.name
        shutil.copy2(src, dst)
        snapshot_manifest[raw] = {
            "snapshot_file": str(dst).replace("\\", "/"),
            "size_bytes": src.stat().st_size,
            "sha256": _sha256(src),
        }

    migration_log = {
        "created_at": datetime.now(UTC).isoformat(),
        "schema_version": "v2.0.0",
        "data_version": f"baseline-{ts}",
        "snapshot_manifest": snapshot_manifest,
        "baseline_metrics": json.loads(Path("storage/dynamic_eval_report.json").read_text(encoding="utf-8")),
    }
    out = Path("storage/v2/migrations/migration_log_v2.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(migration_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
