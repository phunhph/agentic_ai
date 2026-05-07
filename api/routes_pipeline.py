"""
api/routes_pipeline.py
Routes cho pipeline execution và diagnose.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException

from v2.service import run_v2_pipeline

router = APIRouter()


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _compute_graph_compatibility(intent: str, root_table: str) -> dict:
    graph_artifact_path = Path("storage/v2/graph/knowledge_graph_v2.json")
    graph = _read_json_file(graph_artifact_path)
    nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges", []) if isinstance(graph.get("edges"), list) else []
    intent_node = f"intent:{str(intent).strip().lower()}"
    table_node = f"table:{str(root_table).strip()}"

    node_ids = {str(x.get("id", "")) for x in nodes if isinstance(x, dict)}
    has_intent_node = intent_node in node_ids
    has_table_node = table_node in node_ids
    has_maps_edge = any(
        isinstance(e, dict)
        and str(e.get("from", "")) == intent_node
        and str(e.get("to", "")) == table_node
        and str(e.get("type", "")) == "maps_to"
        for e in edges
    )
    score = 0.0
    score += 0.4 if has_intent_node else 0.0
    score += 0.3 if has_table_node else 0.0
    score += 0.3 if has_maps_edge else 0.0
    return {
        "compatibility_score": round(score, 4),
        "intent_node": intent_node,
        "table_node": table_node,
        "has_intent_node": has_intent_node,
        "has_table_node": has_table_node,
        "has_maps_edge": has_maps_edge,
    }


from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates

# ...
templates = Jinja2Templates(directory="web/templates")

from fastapi.responses import HTMLResponse

@router.post("/api/v2/run", response_class=HTMLResponse)
async def run_v2(
    request: Request,
    goal: str = Form(...),
    role: str = Form("DEFAULT"),
    session_id: str = Form(""),
    lang: str = Form("auto"),
):
    try:
        result = run_v2_pipeline(goal, role=role, session_id=session_id, lang=lang)
        return templates.TemplateResponse(
            request=request,
            name="components/trace_result.html",
            context=result
        )
    except Exception as e:
        return f"<div class='p-4 text-red-400'>Error: {str(e)}</div>"


@router.get("/api/v2/system/status")
async def system_status():
    try:
        from pathlib import Path
        import json
        graph_path = Path("storage/v2/dann/agentic_graph.json")
        graph = {}
        if graph_path.exists():
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        
        # Simple extraction of support metrics
        nodes = graph.get("nodes", {})
        support = {k: v.get("support", 0) for k, v in nodes.items()}
        
        return {"ok": True, "matrix_support": support, "version": graph.get("version")}
    except Exception as e:
        return {"ok": False, "detail": str(e)}
