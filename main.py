from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from agent.orchestrator import AgentOrchestrator
from infra.settings import APP_HOST, APP_PORT

app = FastAPI()
orchestrator = AgentOrchestrator()
templates = Jinja2Templates(directory="web/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/run-agent")
async def run_agent(
    goal: str = Form(...),
    role: str = Form("BUYER"),
    history: str = Form("[]"),
    session_id: str = Form(""),
    conversation_id: str = Form(""),
):
    return StreamingResponse(
        orchestrator.run(
            goal=goal,
            role=role,
            history=history,
            session_id=session_id,
            conversation_id=conversation_id,
        ),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(app, host=APP_HOST, port=APP_PORT)
    except KeyboardInterrupt:
        print("\nServer stopped by Ctrl+C")
