# Agentic AI System Architecture (Updated)

This codebase is organized by execution layer and learning loop so planning quality, latency, and safety can evolve without breaking runtime flow.

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

## Agent Loop (Runtime)

1. **Perceive** (`agent/perception.py`)
   - Normalize text.
   - Parse intent/entities.
   - Build request contract.
2. **Reason** (`dynamic_metadata/planner.py` via `agent/orchestrator.py`)
   - Learning-first reuse: apply `knowledge_hits` only when entity/structure are compatible.
   - Intent fast-path: short-circuit tool selection when intent signal is clear.
   - Autonomous scoring fallback: infer tool/args from metadata graph + matrix cases.
   - Build join path and choice constraints when needed.
   - Emit uncertainty trace (`decision_state`, `decision_confidence`, `decision_reason`).
3. **Act** (`agent/action.py`)
   - Enforce policy.
   - Execute tool from `tools/tool_registry.py`.
   - Sanitize output fields and record learning signals.
4. **Evaluate**
   - Validate entity match from output.
   - Penalize wrong lessons/cases.
   - Auto-refresh matrix evaluation.

### Decision State Contract

Planner returns one of:

- `auto_execute`: continue to tool execution.
- `ask_clarify`: orchestrator returns clarify question and skips DB call.
- `safe_block`: planner blocks execution in strict learned-only conditions.

The decision state is available in `planner_trace` and consumed by orchestrator policy handling.

## Dynamic Planner Internals

`dynamic_metadata/planner.py` includes:

- **Caching layer**
  - case match cache
  - entity extraction cache
  - join path cache
- **Uncertainty calibration**
  - base evidence floor
  - learning-score bonus
  - case-success bonus
- **Governance signals**
  - `complexity_score`
  - `complexity_budget`
  - `complexity_budget_exceeded`
  - `rejection_signals`

## Matrix Learning + Eval

Data files:

- `storage/dynamic_cases.json`: learning case matrix.
- `storage/dynamic_eval_report.json`: latest quality report.

Runner:

- `scripts/eval_dynamic_cases.py`

Core metrics:

- `tool_accuracy`
- `path_resolution_success`
- `choice_constraint_success`
- `entity_match_rate`
- `strict_block_rate`
- `decision_state_rate`
- `decision_reason_distribution`
- `avg_calibrated_evidence_floor`
- `latency_ms` (`mean/p50/p95`)

## Design Notes

- `modules/*` folders are the primary implementation surface for domain logic.
- Legacy top-level tool/repository files are thin wrappers to avoid breaking existing imports.
- Current policy uses role-based allowlist in `infra/policy.py`.
- Dynamic planner can ask for clarification instead of over-executing low-signal requests.
- Strict mode remains available to prevent inference beyond learned evidence.

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
