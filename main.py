from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from agent.orchestrator import AgentOrchestrator
from infra.settings import APP_HOST, APP_PORT
from infra.schemas import PlannerFeedbackPayload
from storage.database import SessionLocal
from storage.models import MODEL_MAP

app = FastAPI()
orchestrator = AgentOrchestrator()
templates = Jinja2Templates(directory="web/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


@app.get("/data-console", response_class=HTMLResponse)
async def data_console(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="data_console.html",
        context={"request": request, "tables": sorted(MODEL_MAP.keys())},
    )


def _serialize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize_row(model_obj):
    data = {}
    for col in model_obj.__table__.columns:
        data[col.name] = _serialize_value(getattr(model_obj, col.name))
    return data


@app.get("/api/tables")
async def list_tables():
    return {"tables": sorted(MODEL_MAP.keys())}


@app.get("/api/tables/{table_name}")
async def list_rows(table_name: str, limit: int = 200):
    model = MODEL_MAP.get(table_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Unknown table: {table_name}")
    db = SessionLocal()
    try:
        rows = db.query(model).limit(limit).all()
        return {"rows": [_serialize_row(r) for r in rows]}
    finally:
        db.close()


@app.post("/api/tables/{table_name}")
async def create_row(table_name: str, payload: dict):
    model = MODEL_MAP.get(table_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Unknown table: {table_name}")
    db = SessionLocal()
    try:
        row = model(**payload)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"row": _serialize_row(row)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.put("/api/tables/{table_name}/{row_id}")
async def update_row(table_name: str, row_id: str, payload: dict):
    model = MODEL_MAP.get(table_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Unknown table: {table_name}")
    pk_col = list(model.__table__.primary_key.columns)[0].name
    db = SessionLocal()
    try:
        row = db.query(model).filter(getattr(model, pk_col) == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Row not found")
        for key, val in payload.items():
            if key in model.__table__.columns:
                setattr(row, key, val)
        db.commit()
        db.refresh(row)
        return {"row": _serialize_row(row)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.delete("/api/tables/{table_name}/{row_id}")
async def delete_row(table_name: str, row_id: str):
    model = MODEL_MAP.get(table_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Unknown table: {table_name}")
    pk_col = list(model.__table__.primary_key.columns)[0].name
    db = SessionLocal()
    try:
        row = db.query(model).filter(getattr(model, pk_col) == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Row not found")
        db.delete(row)
        db.commit()
        return {"ok": True}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.post("/run-agent")
async def run_agent(
    goal: str = Form(...),
    role: str = Form("BUYER"),
    history: str = Form("[]"),
    session_id: str = Form(""),
    conversation_id: str = Form(""),
    feedback: str = Form(""),
):
    feedback_lesson_id = None
    if feedback.strip():
        try:
            feedback_payload = PlannerFeedbackPayload.model_validate_json(feedback)
            feedback_lesson_id = orchestrator.ingest_feedback(feedback_payload.model_dump())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid feedback payload: {str(e)}")
    return StreamingResponse(
        orchestrator.run(
            goal=goal,
            role=role,
            history=history,
            session_id=session_id,
            conversation_id=conversation_id,
        ),
        media_type="text/event-stream",
        headers={"X-Feedback-Lesson-Id": feedback_lesson_id or ""},
    )


@app.post("/api/planner-feedback")
async def planner_feedback(payload: PlannerFeedbackPayload):
    try:
        lesson_id = orchestrator.ingest_feedback(payload.model_dump())
        return {"ok": True, "lesson_id": lesson_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(app, host=APP_HOST, port=APP_PORT)
    except KeyboardInterrupt:
        print("\nServer stopped by Ctrl+C")
