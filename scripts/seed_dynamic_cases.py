from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.metadata_provider import get_metadata_provider


def build_cases() -> list[dict]:
    provider = get_metadata_provider()
    cases: list[dict] = []

    cases.append(
        {
            "query": "Lấy danh sách account tuần này cần xử lý",
            "expected_tool": "list_accounts",
            "expected_entities": ["hbl_account"],
        }
    )
    cases.append(
        {
            "query": "Cho tôi các hợp đồng của khách hàng MIMS",
            "expected_tool": "list_contracts",
            "expected_entities": ["hbl_contract", "hbl_account"],
            "expected_path": [
                [
                    {
                        "from_table": edge.from_table,
                        "to_table": edge.to_table,
                        "relation_type": edge.relation_type,
                        "join_table": edge.join_table,
                    }
                    for edge in path
                ]
                for path in provider.find_paths("hbl_contract", "hbl_account", max_depth=4)
            ],
        }
    )

    for group, options in provider._schema.choice_options.items():  # intentional internal metadata usage
        if not options:
            continue
        label = options[0]["label"]
        cases.append(
            {
                "query": f"khách hàng thuộc nhóm {label}",
                "expected_tool": "list_accounts",
                "choice_group": group,
                "choice_label": label,
            }
        )

    return cases


def main() -> None:
    root = ROOT_DIR
    out_path = root / "storage" / "dynamic_cases.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(build_cases(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seeded dynamic cases: {out_path}")


if __name__ == "__main__":
    main()

