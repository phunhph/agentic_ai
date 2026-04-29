"""
DANN Sales Copilot — Main Entry Point.
Chỉ phục vụ V3 DANN endpoints.
"""
import sys
import subprocess
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from infra.settings import APP_HOST, APP_PORT
from v3.service import V3Service

app = FastAPI(title="DANN Sales Copilot", version="3.0")
v3_service = V3Service()
templates = Jinja2Templates(directory="web/templates")


# ── UI Routes ──────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="v3_user.html",
        context={"request": request},
    )


@app.get("/v3/user", response_class=HTMLResponse)
async def v3_user(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="v3_user.html",
        context={"request": request},
    )


@app.get("/v3/trace", response_class=HTMLResponse)
async def v3_trace(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="v3_console.html",
        context={"request": request},
    )


# ── API Routes ─────────────────────────────────────────

@app.post("/api/v3/run")
async def run_v3(
    goal: str = Form(...),
    role: str = Form("DEFAULT"),
    session_id: str = Form(""),
):
    try:
        result = v3_service.run_pipeline(goal, session_id=session_id, role=role)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v3/health")
async def health():
    weights = v3_service.matrix.get_weights()
    top_paths = v3_service.matrix.get_top_paths(limit=5)
    return {
        "ok": True,
        "version": "DANN 3.0",
        "model": v3_service.brain.model,
        "weight_count": len(weights),
        "top_paths": [{"path": p, "weight": w} for p, w in top_paths],
    }


# ── CLI: Dataverse Sync ───────────────────────────────

def _run_dataverse_sync_from_cli(argv: list[str]) -> bool:
    if len(argv) < 4:
        return False
    if argv[1] != "sync" or argv[2] != "dataverse":
        return False

    mode = "bootstrap"
    table_limit = ""
    update_db_json = False
    table_prefix = ""
    tables = ""

    i = 3
    while i < len(argv):
        token = argv[i]
        if token == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1].strip()
            i += 2
            continue
        if token == "--table-limit" and i + 1 < len(argv):
            table_limit = argv[i + 1].strip()
            i += 2
            continue
        if token == "--table-prefix" and i + 1 < len(argv):
            table_prefix = argv[i + 1].strip()
            i += 2
            continue
        if token == "--tables" and i + 1 < len(argv):
            tables = argv[i + 1].strip()
            i += 2
            continue
        if token == "--update-db-json":
            update_db_json = True
            i += 1
            continue
        i += 1

    if mode == "bootstrap":
        cmd = [sys.executable, "v3/scripts/bootstrap_dataverse.py"]
        if table_limit:
            cmd += ["--table-limit", table_limit]
        if table_prefix:
            cmd += ["--table-prefix", table_prefix]
        if tables:
            cmd += ["--tables", tables]
        if update_db_json:
            cmd.append("--update-db-json")
    elif mode in {"full", "incremental"}:
        cmd = [sys.executable, "v3/scripts/sync_dataverse_data.py", "--mode", mode]
        if table_limit:
            cmd += ["--table-limit", table_limit]
        if tables:
            cmd += ["--tables", tables]
    elif mode == "materialize":
        cmd = [sys.executable, "v3/scripts/materialize_v2_runtime.py"]
        if tables:
            cmd += ["--tables", tables]
    elif mode == "refresh-train":
        cmd = [sys.executable, "v3/scripts/refresh_and_train_runtime.py"]
        if tables:
            cmd += ["--tables", tables]
    else:
        raise ValueError("Unsupported mode. Use bootstrap/full/incremental/materialize/refresh-train")

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Dataverse sync failed with exit code {result.returncode}")
    return True


if __name__ == "__main__":
    import uvicorn

    try:
        if _run_dataverse_sync_from_cli(sys.argv):
            raise SystemExit(0)
        uvicorn.run(app, host=APP_HOST, port=APP_PORT)
    except KeyboardInterrupt:
        print("\nServer stopped by Ctrl+C")
