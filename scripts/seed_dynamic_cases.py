from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynamic_metadata.case_seed import build_cases
from dynamic_metadata.paths import dynamic_cases_path


def main() -> None:
    out_path = dynamic_cases_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(build_cases(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seeded dynamic cases: {out_path}")


if __name__ == "__main__":
    main()
