"""Dynamic V2 side-by-side pipeline package."""


def run_v2_pipeline(query: str, role: str = "DEFAULT", session_id: str = "", lang: str = "auto"):
    from v2.service import run_v2_pipeline as _run_v2_pipeline

    return _run_v2_pipeline(query, role=role, session_id=session_id, lang=lang)


__all__ = ["run_v2_pipeline"]
