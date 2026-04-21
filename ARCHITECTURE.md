# Agentic AI System Architecture

This document describes the modular architecture of the Agentic AI system. The codebase is organized by functional responsibility to ensure scalability and maintainability.

## 📁 Directory Structure

```text
.
├── agent/                  # 🧠 Cognitive Core
│   ├── brain.py            # LLM reasoning & decision-making logic
│   ├── orchestrator.py      # Main control loop (Perception -> Reason -> Act -> Eval)
│   ├── perception.py       # Input normalization & intent detection
│   ├── action.py           # Tool execution logic & logging
│   ├── evaluator.py        # Success criteria & loop termination logic
│   └── router.py           # Semantic routing of requests
├── memory/                 # 💾 Memory & Knowledge
│   ├── manager.py          # Episodic memory management
│   ├── vector_store.py     # RAG (Retrieval-Augmented Generation) for DB schemas
│   └── learning.py         # Experience-based learning systems
├── storage/                # 🗄️ Persistence Layer
│   ├── database.py         # SQLAlchemy connection & session management
│   └── models.py           # SQL database schemas
├── infra/                  # 🛠️ Infrastructure & Utilities
│   ├── settings.py         # Environment variables & constants
│   ├── context.py          # Session & conversation management
│   ├── policy.py           # RBAC (Role-Based Access Control) for tools
│   ├── domain.py           # Heuristic domain classification
│   └── schemas.py          # Pydantic models for internal data exchange
├── tools/                  # 🔧 External Capabilities
│   ├── tool_registry.py    # Centralized registration for all agent tools
│   ├── inventory_tool.py   # Inventory management functions
│   └── order_tool.py       # Order processing functions
├── web/                    # 🌐 Presentation Layer
│   └── templates/          # HTML/Frontend components
├── main.py                 # 🚀 Application Entry Point (FastAPI)
├── seed_db.py              # 🌱 Database Seeding Script
└── requirements.txt        # 📦 Dependencies
```

## 🔄 The Agentic Loop

The system operates in a continuous loop managed by the `AgentOrchestrator`:

1.  **Perceive**: Clean the user input and detect the intended role.
2.  **Reason**: Call the LLM (`agent/brain.py`) to decide which tool to use, based on:
    *   Goal & Context
    *   Relevant DB Schemas (from `vector_store`)
    *   Past Experiences (from `learning`)
    *   Short-term Memory (from `manager`)
3.  **Act**: Execute the selected tool in `agent/action.py` (after verifying permissions in `infra/policy.py`).
4.  **Evaluate**: Check if the goal has been reached or if another iteration is needed via `agent/evaluator.py`.

## 🛠️ Key Technologies
- **Logic**: Python 3.10+
- **Agent Reasoning**: Ollama (Llama 3 / Gemma)
- **API Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Intelligence**: Vector Embeddings for semantic search and learning.
