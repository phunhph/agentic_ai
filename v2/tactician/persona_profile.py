from __future__ import annotations


def build_persona_context(role: str = "DEFAULT") -> dict:
    key = str(role or "DEFAULT").strip().upper()
    if key == "JUNIOR":
        return {
            "role": "JUNIOR",
            "experience_level": "junior",
            "tone": "concise_guided",
            "risk_posture": "low",
            "response_style": "closed_choice",
        }
    if key == "SENIOR":
        return {
            "role": "SENIOR",
            "experience_level": "senior",
            "tone": "strategic",
            "risk_posture": "balanced",
            "response_style": "open_strategic",
        }
    return {
        "role": "DEFAULT",
        "experience_level": "default",
        "tone": "neutral",
        "risk_posture": "balanced",
        "response_style": "neutral",
    }
