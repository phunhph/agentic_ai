# DANN — Agentic System (scaffold)

This workspace is a scaffold for a Dynamic Agentic Neural Network style CRM assistant.

Optional integrations
- LangGraph: used to build execution graphs for multi-step reasoning. Install with `pip install langgraph` if available.
- AutoGen: multi-agent orchestration library (install as applicable; placeholder name `autogen` may vary).

Environment variables
- `DANN_LLM_URL`: URL of local/remote LLM endpoint (default: `http://localhost:11434/api/generate`).
- `DANN_DATABASE_URL`: Postgres connection string.
- `LANGGRAPH_API_KEY`: API key for LangGraph (if used).
- `AUTOGEN_API_KEY`: API key for AutoGen (if used).

Quick run (dev)
1. Create a Python virtualenv and install dependencies:
```bash
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```
2. (Optional) Start Postgres or set `DANN_DATABASE_URL`.
3. Initialize DB tables (dev):
```bash
python scripts/init_db.py
```
4. Run the app:
```bash
uvicorn app:app --reload --port 8000
```

UI endpoints
- `/ui/qna` — Q&A feed (polling)
- `/ui/trace` — Trace view for agent/LLM events

Notes
- The LangGraph and AutoGen modules in `core/` are scaffolds. Replace with concrete integration code per your vendor's SDK and API surface.
