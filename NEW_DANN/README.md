# DANN — NextGen CRM AI Copilot

> **D**ata-driven **A**gent for **N**extgen **N**avigation  
> Multi-Agent Sales Copilot · LangGraph + Claude + PostgreSQL

---

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────────────────┐
│                    DANN Architecture                      │
├─────────────┬───────────────────────┬───────────────────┤
│   Frontend  │      Backend          │    Database        │
│  (Web UI)   │   FastAPI + WS        │   PostgreSQL       │
│             │                       │   agentic_store    │
│  Chat UI    │  ┌─── LangGraph ───┐  │                   │
│  Card V2    │  │ Router          │  │  hbl_account       │
│  Replicas   │  │ Gatekeeper      │  │  hbl_opportunities │
│             │  │ Analyst         │  │  hbl_contact       │
│  WebSocket  │◄─│ Operator        │  │  space_member      │
│  Real-time  │  │ Tactician       │  │  chat_message      │
│             │  │ Compass         │  │  audit_log         │
│             │  └─────────────────┘  │  long_term_memory  │
│             │                       │                    │
│             │  Memory System        │                    │
│             │  ├─ Short-term (RAM)  │                    │
│             │  └─ Long-term (DB)    │                    │
└─────────────┴───────────────────────┴───────────────────┘
```

## 🤖 Multi-Agent Flow

```
Message → Router → Gatekeeper → [Analyst | Operator | Tactician | Compass]
           CoT        Confidence     QUERY     UPDATE     STALL      HELP
                      Check          Tree-of-  Chain-of-  Tree-of-   Persona
                      0.85           Thoughts  Thought    Thoughts   Adapt
```

## 🚀 Quick Start

```bash
# 1. Đảm bảo PostgreSQL đang chạy
# DB: postgresql://postgres:123456@localhost:5432/agentic_store

# 2. Set API key
echo "ANTHROPIC_API_KEY=your_key" >> backend/.env

# 3. Start
bash start.sh

# 4. Mở browser
open http://localhost:8000
```

## 📁 Cấu trúc Project

```
dann/
├── backend/
│   ├── agents/
│   │   └── orchestrator.py    # LangGraph multi-agent graph
│   ├── api/
│   │   └── main.py            # FastAPI + WebSocket
│   ├── card_engine/
│   │   └── builder.py         # Google Chat Cards V2 builder
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── repository.py      # CRUD operations
│   │   └── session.py         # DB engine setup
│   ├── memory/
│   │   ├── short_term.py      # Conversation window + debounce
│   │   └── long_term.py       # Playbooks + patterns (DB)
│   └── requirements.txt
├── memory/
│   └── index.html             # Full chat UI (standalone)
└── start.sh
```

## 🧠 Memory Systems

### Short-Term Memory
- Per-sender conversation window (last 10 turns)
- Debounce buffer: nhóm tin nhắn burst trong 5 giây
- Emoji State Machine tracking: ⏳→📊→🛠️→✅

### Long-Term Memory  
- CEO/Senior playbooks (seeded vào DB)
- Pattern storage: deal stall signals, BANT gaps
- Usage-based relevance scoring

## 🤖 Agents

| Node | Intent | Reasoning |
|------|--------|-----------|
| Router | Classify | Chain-of-Thought |
| Gatekeeper | Confidence check | Threshold 0.85 |
| Analyst | QUERY | Tree-of-Thoughts |
| Operator | UPDATE/CREATE | Chain-of-Thought |
| Tactician | Deal stall | Tree-of-Thoughts |
| Compass | HELP/COMPASS | Persona adaptation |

## 🃏 Card Types (Frontend)

1. **BANT Grid** — Direction 1: Data-dense, 2-column grid
2. **Fallback** — Direction 2: Ambiguity resolution, vertical buttons
3. **Pipeline Move** — Direction 3: Linear timeline with undo
4. **Query Result** — Analyst output, key-value rows
5. **Tactician** — Deal stall intervention + email template
6. **Compass** — Daily briefing, junior/senior adaptive

## ⚙️ API Endpoints

```
GET  /api/health
GET  /api/accounts
GET  /api/accounts/{id}/opportunities
GET  /api/pipeline/summary
POST /api/accounts
GET  /api/members
POST /api/members
POST /api/message  (HTTP fallback)
WS   /ws/{sender_id}  (WebSocket)
```

## 🔧 Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://postgres:123456@localhost:5432/agentic_store
ANTHROPIC_API_KEY=your_key
REDIS_URL=redis://localhost:6379  # optional
SECRET_KEY=dann_secret_key
```

## 📋 Design Constraints (từ PRD)

- **DC1**: mixs field queryable by Analyst
- **DC2**: CRM capture NEVER blocks tactical advice
- **DC3**: Tactical first, CRM confirmation secondary
- **DC4**: Trust Firewall — profiler data never exposed to managers
- **DC5**: Junior → closed-choice, Senior → strategic open-ended

## 🗺️ Roadmap

- [x] Phase 1: Foundation — Multi-agent, BANT, SpaceMember
- [ ] Phase 2: Emoji Signaling via Google Chat API reactions
- [ ] Phase 3: Dynamic Sales Profiler, Active Probe
- [ ] Phase 4: Extraction Tactician full pipeline
- [ ] Parallel: Lineage Copilot vector store (CEO playbooks)
