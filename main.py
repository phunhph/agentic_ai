import json
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from infra.settings import APP_HOST, APP_PORT
from v2.service import run_v2_pipeline
from v2.ingest import ingest_query
from v2.reason import reason_about_query
from v2.plan import compile_execution_plan
from v2.execute import validate_execution_plan
from v2.memory import create_session_context, list_session_contexts

app = FastAPI()
templates = Jinja2Templates(directory="web/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="v2_console.html",
        context={"request": request},
    )


@app.get("/v2", response_class=HTMLResponse)
async def v2_console(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="v2_console.html",
        context={"request": request},
    )


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_jsonl_samples(path: Path, limit: int = 10) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out[:limit]


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


@app.get("/api/v2/training/overview")
async def v2_training_overview(sample_limit: int = 10):
    trainset_path = Path("storage/v2/matrix/trainset_v2.jsonl")
    matrix_artifact_path = Path("storage/v2/matrix/matrix_v2_artifact.json")
    matrix_eval_path = Path("storage/v2/matrix/matrix_v2_eval.json")
    graph_artifact_path = Path("storage/v2/graph/knowledge_graph_v2.json")
    graph_eval_path = Path("storage/v2/graph/knowledge_graph_v2_eval.json")

    train_samples = _read_jsonl_samples(trainset_path, limit=max(1, min(sample_limit, 50)))
    matrix_artifact = _read_json_file(matrix_artifact_path)
    matrix_eval = _read_json_file(matrix_eval_path)
    graph_artifact = _read_json_file(graph_artifact_path)
    graph_eval = _read_json_file(graph_eval_path)

    graph_nodes = graph_artifact.get("nodes", []) if isinstance(graph_artifact.get("nodes"), list) else []
    graph_edges = graph_artifact.get("edges", []) if isinstance(graph_artifact.get("edges"), list) else []

    return {
        "status": "ok",
        "files": {
            "trainset_exists": trainset_path.exists(),
            "matrix_artifact_exists": matrix_artifact_path.exists(),
            "matrix_eval_exists": matrix_eval_path.exists(),
            "graph_artifact_exists": graph_artifact_path.exists(),
            "graph_eval_exists": graph_eval_path.exists(),
        },
        "matrix": {
            "artifact": matrix_artifact,
            "eval": matrix_eval,
        },
        "graph": {
            "artifact_meta": {
                "version": graph_artifact.get("version"),
                "node_count": graph_artifact.get("node_count", 0),
                "edge_count": graph_artifact.get("edge_count", 0),
            },
            "eval": graph_eval,
            "top_nodes": graph_nodes[:10],
            "top_edges": graph_edges[:10],
        },
        "trainset_preview": {
            "sample_count": len(train_samples),
            "samples": train_samples,
        },
    }


@app.post("/api/v2/run")
async def run_v2(
    goal: str = Form(...),
    role: str = Form("DEFAULT"),
    session_id: str = Form(""),
    lang: str = Form("auto"),
):
    try:
        result = run_v2_pipeline(goal, role=role, session_id=session_id, lang=lang)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v2/diagnose")
async def diagnose_v2(goal: str = Form(...), role: str = Form("DEFAULT"), action_hint: str = Form("")):
    try:
        ingest = ingest_query(goal, role=role)
        reason_result = reason_about_query(ingest)
        plan = compile_execution_plan(ingest, reason_result)
        validation = validate_execution_plan(plan)
        graph_alignment = _compute_graph_compatibility(ingest.intent, plan.root_table)

        action_contract = {
            "action_hint": action_hint,
            "input_goal": goal,
            "predicted_behavior": {
                "root_table": plan.root_table,
                "join_path_size": len(plan.join_path),
                "filter_count": len(plan.where_filters),
                "limit": plan.limit,
            },
            "guardrail_ok": validation.ok,
            "guardrail_errors": validation.errors,
            "guardrail_warnings": validation.warnings,
        }
        return {
            "ok": True,
            "diagnostic": {
                "ingest": {
                    "intent": ingest.intent,
                    "entities": ingest.entities,
                    "ambiguity_score": ingest.ambiguity_score,
                    "request_filters": [f.__dict__ for f in ingest.request_filters],
                },
                "knowledge_alignment": graph_alignment,
                "planner_trace_v2": reason_result.get("planner_trace_v2", {}),
                "action_contract": action_contract,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v2/contexts")
async def list_v2_contexts(limit: int = 100):
    try:
        items = list_session_contexts(limit=limit)
        return {"ok": True, "contexts": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v2/contexts")
async def create_v2_context(session_id: str = Form(...)):
    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        row = create_session_context(sid)
        return {"ok": True, "context": row}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(app, host=APP_HOST, port=APP_PORT)
    except KeyboardInterrupt:
        print("\nServer stopped by Ctrl+C")
