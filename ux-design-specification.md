# UI Design Specification: Agentic Trace Console

## 1. Goal
Replace hardcoded UI with a dynamic, observable console that allows real-time tracing of agentic phases (Ingest, Reason, Plan, Execute, Learn).

## 2. Technology Stack
- **Frontend:** Vanilla HTML5 + Tailwind CSS (for quick, responsive layout) + HTMX (for dynamic, non-polling updates).
- **Backend:** FastAPI (Existing).

## 3. Core Features
- **Phase Timeline:** A visual representation of the agent's current phase.
- **Trace Logs:** A panel showing JSON-based logs/metadata for each step.
- **Live State:** Real-time status indicators (Working, Success, Error).

## 4. UI Layout (Mockup)
- **Top Bar:** Input area (Goal, Role, Session).
- **Left Panel:** Live Trace timeline (Ingestion -> Reasoning -> Planning -> Execution -> Learning).
- **Right Panel:** Detailed log/trace output (expandable blocks).
- **Bottom Bar:** Agentic Status / Health.

## 5. Implementation Path
- Create `web/templates/v2_console_new.html`.
- Update API endpoints to include `trace_data` in response.
- Use HTMX to refresh UI blocks as the pipeline progresses.
