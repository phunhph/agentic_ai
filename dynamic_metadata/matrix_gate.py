"""Cổng ma trận: Kiểm soát chất lượng động theo cấu hình env."""

from __future__ import annotations
import json
from infra import settings # Load toàn bộ cấu trúc config
from dynamic_metadata.paths import dynamic_eval_report_path

def evaluate_matrix_gate() -> tuple[bool, dict]:
    # 1. Kiểm tra công tắc tổng
    if not getattr(settings, "ENABLE_MATRIX_GATE", False):
        return True, {"enabled": False, "reason": "Gate is bypassed"}

    report_path = dynamic_eval_report_path()
    if not report_path.exists():
        return False, {"enabled": True, "reason": "Missing eval report"}

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        return False, {"enabled": True, "reason": "Report corrupted"}

    # 2. Cơ chế Dynamic Validation (Lean Logic)
    # Lấy danh sách các chỉ số cần kiểm tra từ settings (Ví dụ: MATRIX_CHECK_LIST = ["tool_accuracy", ...])
    # Điều này giúp ông thêm chỉ số mới mà không cần sửa file này.
    check_list = getattr(
        settings,
        "MATRIX_METRICS_TO_CHECK",
        ["tool_accuracy", "path_resolution_success", "choice_constraint_success"],
    )
    
    results = {}
    passed = True

    for metric in check_list:
        current_value = float(report.get(metric, 0.0))
        # Tự động tìm ngưỡng tương ứng trong settings: MATRIX_MIN_{METRIC_NAME}
        threshold_name = f"MATRIX_MIN_{metric.upper()}"
        threshold_value = getattr(settings, threshold_name, None)
        if threshold_value is None:
            alias_threshold_name = {
                "tool_accuracy": "MATRIX_MIN_TOOL_ACCURACY",
                "path_resolution_success": "MATRIX_MIN_PATH_SUCCESS",
                "choice_constraint_success": "MATRIX_MIN_CHOICE_SUCCESS",
                "entity_match_rate": "MATRIX_MIN_ENTITY_MATCH_RATE",
            }.get(metric, "")
            threshold_value = getattr(settings, alias_threshold_name, None) if alias_threshold_name else None
        if threshold_value is None:
            threshold_value = getattr(settings, "MATRIX_DEFAULT_THRESHOLD", 0.8)
        
        results[metric] = {
            "current": current_value,
            "threshold": threshold_value,
            "ok": current_value >= threshold_value
        }
        
        if current_value < threshold_value:
            passed = False

    return passed, {
        "enabled": True,
        "passed": passed,
        "details": results,
        "summary": "Dynamic Planner Authorized" if passed else "Quality Insufficient"
    }