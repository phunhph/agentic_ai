import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from infra.settings import APP_HOST, APP_PORT, get_env_int
from v2.service import run_v2_pipeline
from v2.ingest import ingest_query
from v2.ingest.pubsub_ingress import publish_event
from v2.ingest.pubsub_worker import process_event
from v2.reason import reason_about_query
from v2.plan import compile_execution_plan
from v2.execute import validate_execution_plan
from v2.lifecycle import LIFECYCLE_STORE
from v2.memory import clear_all_session_contexts, create_session_context, delete_session_context, list_session_contexts

app = FastAPI()
templates = Jinja2Templates(directory="web/templates")
EVENT_ACK_SLA_MS = get_env_int("EVENT_ACK_SLA_MS", 1500)


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
    # Show latest runtime samples first so dashboard reflects current learning,
    # not old bootstrap rows that can bias toward unknown intents.
    return list(reversed(out))[:limit]


def _iso_mtime(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    except Exception:
        return ""


def _read_latest_auto_train_summary() -> dict:
    logs_dir = Path("storage/v2/training/auto_train_logs")
    if not logs_dir.exists():
        return {}
    summaries = sorted(logs_dir.glob("*_summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not summaries:
        return {}
    latest = summaries[0]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
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
    latest_auto_train = _read_latest_auto_train_summary()

    graph_nodes = graph_artifact.get("nodes", []) if isinstance(graph_artifact.get("nodes"), list) else []
    graph_edges = graph_artifact.get("edges", []) if isinstance(graph_artifact.get("edges"), list) else []
    graph_nodes_sorted = sorted(
        [n for n in graph_nodes if isinstance(n, dict)],
        key=lambda n: float(n.get("support", 0) or 0),
        reverse=True,
    )
    graph_edges_sorted = sorted(
        [e for e in graph_edges if isinstance(e, dict)],
        key=lambda e: float(e.get("support", 0) or 0),
        reverse=True,
    )

    return {
        "status": "ok",
        "files": {
            "trainset_exists": trainset_path.exists(),
            "matrix_artifact_exists": matrix_artifact_path.exists(),
            "matrix_eval_exists": matrix_eval_path.exists(),
            "graph_artifact_exists": graph_artifact_path.exists(),
            "graph_eval_exists": graph_eval_path.exists(),
            "trainset_mtime": _iso_mtime(trainset_path),
            "matrix_artifact_mtime": _iso_mtime(matrix_artifact_path),
            "matrix_eval_mtime": _iso_mtime(matrix_eval_path),
        },
        "runtime_training": {
            "latest_auto_train_summary": latest_auto_train,
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
            "top_nodes": graph_nodes_sorted[:10],
            "top_edges": graph_edges_sorted[:10],
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


@app.post("/api/v2/events/publish")
async def publish_v2_event(
    background_tasks: BackgroundTasks,
    goal: str = Form(...),
    role: str = Form("DEFAULT"),
    session_id: str = Form(""),
    lang: str = Form("auto"),
    source: str = Form("pubsub"),
):
    payload = {
        "goal": goal,
        "role": role,
        "session_id": session_id,
        "lang": lang,
        "source": source,
    }
    event = publish_event(payload, ack_sla_ms=EVENT_ACK_SLA_MS)
    event_id = str(event.get("event_id", ""))
    background_tasks.add_task(process_event, event_id, goal, role, session_id, lang)
    return {"ok": True, "event": event}


@app.get("/api/v2/events/{event_id}")
async def get_v2_event(event_id: str):
    state = LIFECYCLE_STORE.get(event_id)
    if not state:
        raise HTTPException(status_code=404, detail="event_not_found")
    return {"ok": True, "event": state}


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


@app.delete("/api/v2/contexts/{session_id}")
async def delete_v2_context(session_id: str):
    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        removed = delete_session_context(sid)
        return {"ok": True, "deleted": bool(removed), "session_id": sid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v2/contexts")
async def clear_v2_contexts():
    try:
        deleted_count = clear_all_session_contexts()
        return {"ok": True, "deleted_count": int(deleted_count)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(app, host=APP_HOST, port=APP_PORT)
    except KeyboardInterrupt:
        print("\nServer stopped by Ctrl+C")
