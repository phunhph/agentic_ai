from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_step(name: str, cmd: list[str]) -> None:
    print(f"[REFRESH-TRAIN] {name}")
    print(f"[REFRESH-TRAIN] CMD: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {name} (exit={result.returncode})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh Dataverse runtime data, update choice map, retrain and run regression trials."
    )
    parser.add_argument(
        "--tables",
        default="hbl_account,hbl_contact,hbl_opportunities,hbl_contract,systemuser",
        help="Comma-separated logical table names",
    )
    parser.add_argument("--train-rounds", type=int, default=1)
    parser.add_argument("--variant-factor", type=int, default=2)
    parser.add_argument("--max-scenarios", type=int, default=18)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--chunk-size", type=int, default=4, help="Train scenarios per chunk.")
    parser.add_argument("--chunk-count", type=int, default=3, help="How many chunks to run.")
    parser.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help="Data sync mode before retrain.",
    )
    args = parser.parse_args()

    _run_step(
        "Sync Dataverse data",
        [
            sys.executable,
            "main.py",
            "sync",
            "dataverse",
            "--mode",
            args.mode,
            "--tables",
            args.tables,
        ],
    )

    _run_step(
        "Materialize runtime DB",
        [
            sys.executable,
            "main.py",
            "sync",
            "dataverse",
            "--mode",
            "materialize",
            "--tables",
            args.tables,
        ],
    )

    _run_step(
        "Update db.json choice options",
        [
            sys.executable,
            "v3/scripts/update_choice_options_from_staging.py",
        ],
    )

    _run_step(
        "Audit choice quality",
        [
            sys.executable,
            "v3/scripts/audit_choice_quality.py",
            "--tables",
            args.tables,
        ],
    )

    chunk_size = max(1, int(args.chunk_size))
    chunk_count = max(1, int(args.chunk_count))
    max_scenarios = max(1, int(args.max_scenarios))
    for idx in range(chunk_count):
        offset = idx * chunk_size
        _run_step(
            f"Auto-train runtime cases (chunk {idx + 1}/{chunk_count})",
            [
                sys.executable,
                "scripts/auto_train_runtime_cases.py",
                "--rounds",
                str(args.train_rounds),
                "--variant-factor",
                str(args.variant_factor),
                "--max-scenarios",
                str(min(chunk_size, max_scenarios)),
                "--scenario-offset",
                str(offset),
                "--timeout-seconds",
                str(max(10, int(args.timeout_seconds))),
                "--no-auto-retry-failures",
            ],
        )

    _run_step(
        "Run regression trial",
        [
            sys.executable,
            "scripts/regression_v2_runtime.py",
        ],
    )

    print("[REFRESH-TRAIN] Completed successfully.")


if __name__ == "__main__":
    main()
