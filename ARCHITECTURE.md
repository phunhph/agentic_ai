# Agentic AI System Architecture

This codebase is organized by layer and by domain module to keep planning, execution, and data access easy to maintain.

## Directory Map (Current)

```text
.
├── agent/                               # Orchestrator + Agent loop nodes
│   ├── orchestrator.py                  # Perceive -> Reason -> Act -> Eval loop
│   ├── perception.py                    # Intent + entity extraction, request normalization
│   ├── dynamic_planner.py               # Bridge to dynamic metadata planner
│   ├── action.py                        # Tool execution + policy guard + learning logs
│   ├── evaluator.py                     # Stop/continue decision
│   └── field_resolver.py                # Intent -> tool_hint + normalized entities
├── dynamic_metadata/                    # Dynamic planner and matrix learning
│   ├── planner.py                       # Verify-before-reuse planner
│   ├── entity_extract.py                # Identity-first extraction
│   ├── matrix_gate.py                   # Gate by evaluation metrics
│   ├── matrix_learning.py               # Auto-update + penalty/prune cases
│   ├── eval_runner.py                   # Eval matrix cases -> report
│   └── case_seed.py                     # Seed baseline dynamic cases
├── tools/
│   ├── tool_registry.py                 # Single source of tool metadata/arg mapping
│   ├── modules/                         # Primary tool implementations by domain
│   │   ├── accounts.py
│   │   ├── contacts.py
│   │   └── contracts.py
│   ├── inventory_tool.py                # Compatibility wrapper -> modules.accounts
│   ├── contact_tool.py                  # Compatibility wrapper -> modules.contacts
│   └── order_tool.py                    # Compatibility wrapper -> modules.contracts
├── storage/
│   ├── database.py                      # SQLAlchemy engine/session
│   ├── models/                          # ORM models
│   ├── repositories/
│   │   ├── modules/                     # Primary repository implementations by domain
│   │   │   ├── accounts.py
│   │   │   ├── contacts.py
│   │   │   └── contracts.py
│   │   ├── account_repository.py        # Compatibility wrapper -> modules.accounts
│   │   ├── contact_repository.py        # Compatibility wrapper -> modules.contacts
│   │   ├── contract_repository.py       # Compatibility wrapper -> modules.contracts
│   │   └── knowledge_repository.py      # Learned lessons in DB
│   ├── dynamic_cases.json               # Learned case matrix
│   └── dynamic_eval_report.json         # Matrix quality metrics
├── memory/                              # Episodic + vector memory
├── infra/                               # Settings, policy, context, schemas
├── web/templates/                       # UI
├── main.py                              # FastAPI entrypoint
└── scripts/                             # Seed/eval helper scripts
```

## Agent Loop

1. **Perceive** (`agent/perception.py`)
   - Normalize text.
   - Parse intent/entities.
   - Build request contract.
2. **Reason** (`dynamic_metadata/planner.py` via `agent/orchestrator.py`)
   - Reuse lessons only when entities are compatible.
   - Otherwise infer tool/args from metadata graph + matrix cases.
3. **Act** (`agent/action.py`)
   - Enforce policy.
   - Execute tool from `tools/tool_registry.py`.
   - Sanitize output fields and record learning signals.
4. **Evaluate**
   - Validate entity match from output.
   - Penalize wrong lessons/cases.
   - Auto-refresh matrix evaluation.

## Design Notes

- `modules/*` folders are the primary implementation surface for domain logic.
- Legacy top-level tool/repository files are thin wrappers to avoid breaking existing imports.
- Current policy is single-role (`DEFAULT`) with tool allowlist controlled in `infra/policy.py`.

## Import Conventions (Team Standard)

- For new code, import tool functions from `tools.modules` (package-level API), not from wrapper files.
- For new code, import data access functions from `storage.repositories.modules` (or its domain files), not legacy repository wrappers.
- Keep wrapper files only for backward compatibility; do not add new logic there.

Examples:

```python
# Preferred
from tools.modules import list_accounts, create_contact
from storage.repositories.modules import search_accounts_with_rollup, list_contacts_with_context

# Legacy compatibility only (avoid for new code)
from tools.inventory_tool import list_accounts
from storage.repositories.account_repository import search_accounts_with_rollup
```
