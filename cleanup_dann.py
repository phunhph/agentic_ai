"""
DANN Cleanup Script - Xóa toàn bộ file/thư mục không cần thiết.
Chạy: python cleanup_dann.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).parent

# 1. Thư mục xóa hoàn toàn
DIRS_TO_DELETE = [
    ROOT / "v3" / "agent",
    ROOT / "scratch",
    ROOT / "v2" / "ingest",
    ROOT / "v2" / "reason",
    ROOT / "v2" / "plan",
    ROOT / "v2" / "eval",
    ROOT / "v2" / "learn",
    ROOT / "v2" / "lifecycle",
    ROOT / "v2" / "tactician",
    ROOT / "scripts",
]

# 2. File xóa
FILES_TO_DELETE = [
    # Root-level legacy docs
    ROOT / "TEST_CASES_V2_SPACE_MESSAGES.md",
    ROOT / "test_flows_runtime_v2.md",
    ROOT / "plan_auto_clone_dataverse.md",
    ROOT / "ux-design-directions.html",
    ROOT / "ux-design-specification.md",
    ROOT / "space_messages.json",
    # V3 legacy docs
    ROOT / "v3" / "HUONG_DAN_LAY_THONG_TIN_DANG_NHAP_DATAVERSE.md",
    ROOT / "v3" / "README.md",
    ROOT / "v3" / "RUNBOOK_DATAVERSE_SYNC.md",
    ROOT / "v3" / "plan_auto_clone_dataverse.md",
    # V2 files to delete (keeping contracts.py, metadata.py, execute/, __init__.py)
    ROOT / "v2" / "service.py",
    ROOT / "v2" / "memory.py",
    # V2 web templates
    ROOT / "web" / "templates" / "v2_console.html",
    ROOT / "web" / "templates" / "v2_user.html",
    # Old storage eval files
    ROOT / "storage" / "dynamic_cases.json",
    ROOT / "storage" / "golden_cases.json",
    ROOT / "storage" / "golden_cases_eval.json",
]

deleted_dirs = 0
deleted_files = 0

for d in DIRS_TO_DELETE:
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        print(f"  [DIR DELETED] {d.relative_to(ROOT)}")
        deleted_dirs += 1

for f in FILES_TO_DELETE:
    if f.exists():
        f.unlink()
        print(f"  [FILE DELETED] {f.relative_to(ROOT)}")
        deleted_files += 1

print(f"\nDone: {deleted_dirs} directories, {deleted_files} files deleted.")
