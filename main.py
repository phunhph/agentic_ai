"""
main.py
FastAPI app bootstrap — chỉ app creation + include routers + UI routes.
"""
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from infra.settings import APP_HOST, APP_PORT
from api.routes_pipeline import router as pipeline_router
from api.routes_training import router as training_router
from api.routes_events import router as events_router
from api.routes_context import router as context_router

app = FastAPI(title="Agentic AI", version="2.0")
templates = Jinja2Templates(directory="web/templates")

# Include routers
app.include_router(pipeline_router)
app.include_router(training_router)
app.include_router(events_router)
app.include_router(context_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="v2_console_new.html",
        context={"request": request},
    )


@app.get("/v2", response_class=HTMLResponse)
async def v2_console(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="v2_console_new.html",
        context={"request": request},
    )


if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(app, host=APP_HOST, port=APP_PORT)
    except KeyboardInterrupt:
        print("\nServer stopped by Ctrl+C")
