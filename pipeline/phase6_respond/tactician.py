"""
phase6_respond/tactician.py
Tách từ v2/service.py — apply tactician layer và lean personalization lên response.
"""
from __future__ import annotations


def apply_tactician_layer(text: str, tactician_payload: dict, locale: str = "vi") -> str:
    """Append tactician next steps và probe questions vào cuối response."""
    if not isinstance(tactician_payload, dict):
        return text
    next_steps = tactician_payload.get("recommended_next_steps", [])
    probe_questions = tactician_payload.get("probe_questions", [])
    signals = tactician_payload.get("signals", {}) if isinstance(tactician_payload.get("signals"), dict) else {}
    if not isinstance(next_steps, list):
        next_steps = []
    if not isinstance(probe_questions, list):
        probe_questions = []
    exact_match = bool(signals.get("exact_match", False))

    step_lines = [f"- {str(x).strip()}" for x in next_steps[:3] if str(x).strip()]
    probe_lines = [f"- {str(x).strip()}" for x in probe_questions[:2] if str(x).strip()]
    if locale == "en":
        out = text
        if step_lines:
            title = "Tactician exploitation steps" if exact_match else "Tactician next steps"
            out += f"\n\n{title}:\n" + "\n".join(step_lines)
        if probe_lines:
            out += "\n\nTactician probes:\n" + "\n".join(probe_lines)
        return out

    out = text
    if step_lines:
        title = "Gợi ý khai thác tiếp theo" if exact_match else "Gợi ý Extraction Tactician"
        out += f"\n\n{title}:\n" + "\n".join(step_lines)
    if probe_lines:
        out += "\n\nCâu hỏi thăm dò:\n" + "\n".join(probe_lines)
    return out


def apply_lean_personalization(text: str, role: str, locale: str = "vi") -> str:
    """Adapt response scaffolding theo role (JUNIOR/SENIOR/DEFAULT)."""
    role_key = str(role or "DEFAULT").strip().upper()
    if role_key == "JUNIOR":
        if locale == "en":
            return "💡 **Quick guidance**\n1) Confirm the exact target record.\n2) Add one concrete filter.\n3) Re-run.\n\n" + text
        return "💡 **Hướng dẫn nhanh**\n1) Xác nhận đúng đối tượng.\n2) Thêm 1 điều kiện lọc cụ thể.\n3) Chạy lại truy vấn.\n\n" + text
    if role_key == "SENIOR":
        if locale == "en":
            return "🚀 **Strategic lens**\nPrioritize signal quality (entity + high-confidence filter) before expanding scope.\n\n" + text
        return "🚀 **Góc nhìn chiến lược**\nƯu tiên chất lượng tín hiệu (đúng entity + filter chắc chắn) trước khi mở rộng phạm vi.\n\n" + text
    return text


# Aliases cho backwards compat
_apply_tactician_layer = apply_tactician_layer
_apply_lean_personalization = apply_lean_personalization
