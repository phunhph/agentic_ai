from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def storage_dir() -> Path:
    return _PROJECT_ROOT / "storage"


def dynamic_cases_path() -> Path:
    return storage_dir() / "dynamic_cases.json"


def dynamic_eval_report_path() -> Path:
    return storage_dir() / "dynamic_eval_report.json"
