from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from storage.database import SessionLocal
from storage.models.agent_knowledge_base import AgentKnowledgeBase


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.query(AgentKnowledgeBase).all()
        for row in rows:
            usage = max(1, int(row.usage_count or 0))
            success = int(row.success_count or 0)
            success_ratio = success / usage
            volume_bonus = min(0.3, usage / 100.0)
            row.score = round(success_ratio + volume_bonus, 4)
            row.is_active = row.score >= 0.15 or usage < 5
        db.commit()
        print(f"Refreshed knowledge scores for {len(rows)} lessons.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

