"""
DANN - FastAPI Application
REST API + WebSocket for real-time chat interface
"""
from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agents.orchestrator import AgentState, dann_graph
from card_engine.builder import CardViewEngine
from db.models import ChatMessage
from db.repository import (
    account_repo, audit_repo, opportunity_repo, space_member_repo
)
from db.session import get_db, init_db
from memory.long_term import long_term_memory
from memory.short_term import short_term_memory


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    await init_db()
    # Seed long-term memories
    from db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await long_term_memory.seed_default_playbooks(session)
        await session.commit()
    print("✅ DANN initialized")
    yield
    print("🛑 DANN shutting down")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DANN - NextGen CRM AI",
    description="Multi-Agent Sales Copilot powered by LangGraph + Claude",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, sender_id: str, ws: WebSocket):
        await ws.accept()
        self.active[sender_id] = ws

    def disconnect(self, sender_id: str):
        self.active.pop(sender_id, None)

    async def send(self, sender_id: str, data: dict):
        ws = self.active.get(sender_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(sender_id)

    async def broadcast(self, data: dict):
        for sender_id in list(self.active.keys()):
            await self.send(sender_id, data)


manager = ConnectionManager()

EMOJI_STATES = {
    "queued": "⏳",
    "analyzing": "📊",
    "processing": "🛠️",
    "done": "✅",
    "ambiguous": "❓",
    "error": "❌",
}


async def emit_state(sender_id: str, message_id: str, state: str, extra: dict = None):
    """Push emoji state machine updates via WebSocket"""
    payload = {
        "type": "state_update",
        "message_id": message_id,
        "state": state,
        "emoji": EMOJI_STATES.get(state, ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    await manager.send(sender_id, payload)


# ─── Core Message Processor ───────────────────────────────────────────────────

async def process_message(
    sender_id: str,
    space_id: str,
    text: str,
    message_id: str,
    db: AsyncSession,
):
    """Main processing pipeline with emoji state machine"""

    # State: queued
    await emit_state(sender_id, message_id, "queued")

    # Fetch sender profile
    member = await space_member_repo.get_by_sender_id(db, sender_id)
    sender_profile = space_member_repo.to_dict(member) if member else {
        "sender_id": sender_id,
        "display_name": sender_id,
        "experience_level": "junior",
        "role": "sales_rep",
    }

    # State: analyzing
    await emit_state(sender_id, message_id, "analyzing")

    # Get conversation history
    history_messages = short_term_memory.get_langchain_messages(sender_id, space_id)

    # Initial state for graph
    initial_state: AgentState = {
        "messages": history_messages,
        "sender_id": sender_id,
        "space_id": space_id,
        "raw_text": text,
        "intent": None,
        "confidence": None,
        "extracted_entities": None,
        "needs_clarification": False,
        "clarification_options": None,
        "clarification_question": None,
        "matched_account": None,
        "matched_opportunity": None,
        "sender_profile": sender_profile,
        "reasoning_trace": None,
        "card_response": None,
        "plain_response": None,
        "error": None,
    }

    # Entity resolution before graph (find account in DB)
    try:
        # Quick entity pre-fetch (will be refined by router)
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage
        import os
        llm_quick = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0,
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            max_tokens=200,
        )
        quick_resp = await llm_quick.ainvoke([
            SystemMessage(content='Extract account name only. Return JSON: {"account_name": "...or null"}'),
            HumanMessage(content=text),
        ])
        import re
        raw = re.sub(r"```json|```", "", quick_resp.content).strip()
        quick_data = json.loads(raw)
        acc_name = quick_data.get("account_name")
        if acc_name:
            accounts = await account_repo.find_by_name(db, acc_name)
            if len(accounts) == 1:
                initial_state["matched_account"] = account_repo.to_dict(accounts[0])
                # Get latest opportunity
                opps = await opportunity_repo.find_by_account(db, accounts[0].hbl_accountid)
                if opps:
                    initial_state["matched_opportunity"] = opportunity_repo.to_dict(opps[0])
            elif len(accounts) > 1:
                # Multiple matches -> will trigger gatekeeper
                initial_state["matched_account"] = {"_multiple": [account_repo.to_dict(a) for a in accounts]}
    except Exception:
        pass

    # State: processing
    await emit_state(sender_id, message_id, "processing")

    # Run LangGraph
    try:
        result = await dann_graph.ainvoke(initial_state)
    except Exception as e:
        result = {**initial_state, "error": str(e)}

    # Determine final state
    if result.get("error") and not result.get("card_response"):
        final_state = "error"
    elif result.get("needs_clarification"):
        final_state = "ambiguous"
    else:
        final_state = "done"

    card_response = result.get("card_response")

    # Store conversation turn in short-term memory
    short_term_memory.add_turn(
        sender_id, space_id, "user", text, intent=result.get("intent")
    )
    if card_response:
        short_term_memory.add_turn(
            sender_id, space_id, "assistant",
            result.get("plain_response", "Card response"),
            card_type=final_state,
        )

    # State: done/error/ambiguous
    await emit_state(sender_id, message_id, final_state, {
        "card": card_response,
        "intent": result.get("intent"),
        "confidence": result.get("confidence"),
        "reasoning": result.get("reasoning_trace"),
    })

    # Persist to DB (async, non-blocking)
    try:
        msg = ChatMessage(
            id=uuid.UUID(message_id),
            sender_id=sender_id,
            space_id=space_id,
            message_text=text,
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            processing_state=final_state,
            agent_response=card_response,
            related_account_id=(
                uuid.UUID(result["matched_account"]["hbl_accountid"])
                if result.get("matched_account") and "hbl_accountid" in (result.get("matched_account") or {})
                else None
            ),
            processed_at=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.commit()
    except Exception:
        pass


# ─── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/{sender_id}")
async def websocket_endpoint(
    ws: WebSocket,
    sender_id: str,
    db: AsyncSession = Depends(get_db),
):
    await manager.connect(sender_id, ws)
    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "message")

            if msg_type == "message":
                text = raw.get("text", "").strip()
                space_id = raw.get("space_id", "default_space")
                message_id = str(uuid.uuid4())

                if not text:
                    continue

                # Check if @DANN mention → immediate processing
                is_mention = "@dann" in text.lower() or "@agent" in text.lower()

                if is_mention:
                    asyncio.create_task(
                        process_message(sender_id, space_id, text, message_id, db)
                    )
                else:
                    # Debounce non-mention messages
                    async def debounced_process(merged_text: str):
                        mid = str(uuid.uuid4())
                        await process_message(sender_id, space_id, merged_text, mid, db)

                    await short_term_memory.buffer_message(
                        sender_id, space_id, text, debounced_process
                    )
                    # Send queued ack immediately
                    await emit_state(sender_id, message_id, "queued")

            elif msg_type == "card_action":
                action_id = raw.get("action_id", "")
                payload = raw.get("payload", {})
                message_id = str(uuid.uuid4())

                # Handle card button actions
                if action_id == "action_undo":
                    orig_msg_id = payload.get("message_id")
                    if orig_msg_id:
                        try:
                            success = await audit_repo.undo_last(db, uuid.UUID(orig_msg_id))
                            await db.commit()
                            await manager.send(sender_id, {
                                "type": "undo_result",
                                "success": success,
                                "message": "Đã hoàn tác thành công ✅" if success else "Không có gì để hoàn tác",
                            })
                        except Exception as e:
                            await manager.send(sender_id, {"type": "error", "message": str(e)})
                elif action_id.startswith("resolve_option_"):
                    # User selected from fallback card
                    selected = payload.get("account_name") or payload.get("value", "")
                    await process_message(
                        sender_id, space_id=raw.get("space_id", "default_space"),
                        text=selected, message_id=message_id, db=db,
                    )
                elif action_id == "action_view_detail":
                    acc_name = payload.get("account_name", "")
                    accounts = await account_repo.find_by_name(db, acc_name)
                    if accounts:
                        acc = accounts[0]
                        opps = await opportunity_repo.find_by_account(db, acc.hbl_accountid)
                        await manager.send(sender_id, {
                            "type": "detail_view",
                            "account": account_repo.to_dict(acc),
                            "opportunities": [opportunity_repo.to_dict(o) for o in opps],
                        })

    except WebSocketDisconnect:
        manager.disconnect(sender_id)


# ─── REST API Endpoints ────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    text: str
    sender_id: str
    space_id: str = "default"


@app.post("/api/message")
async def send_message(req: MessageRequest, db: AsyncSession = Depends(get_db)):
    """HTTP fallback for message processing"""
    message_id = str(uuid.uuid4())
    asyncio.create_task(
        process_message(req.sender_id, req.space_id, req.text, message_id, db)
    )
    return {"message_id": message_id, "status": "queued"}


@app.get("/api/accounts")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    accounts = await account_repo.list_all(db)
    return [account_repo.to_dict(a) for a in accounts]


@app.get("/api/accounts/{account_id}/opportunities")
async def get_opportunities(account_id: str, db: AsyncSession = Depends(get_db)):
    opps = await opportunity_repo.find_by_account(db, uuid.UUID(account_id))
    return [opportunity_repo.to_dict(o) for o in opps]


@app.get("/api/pipeline/summary")
async def pipeline_summary(db: AsyncSession = Depends(get_db)):
    return await opportunity_repo.get_pipeline_summary(db)


@app.get("/api/members")
async def list_members(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from db.models import SpaceMember
    result = await db.execute(select(SpaceMember))
    members = result.scalars().all()
    return [space_member_repo.to_dict(m) for m in members]


@app.post("/api/members")
async def create_member(
    sender_id: str,
    display_name: str,
    role: str = "sales_rep",
    experience_level: str = "junior",
    db: AsyncSession = Depends(get_db),
):
    member = await space_member_repo.upsert(
        db, sender_id, display_name,
        role=role, experience_level=experience_level,
    )
    await db.commit()
    return space_member_repo.to_dict(member)


@app.post("/api/accounts")
async def create_account(
    name: str,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.create(
        db, name,
        mc_account_industry=industry,
        mc_account_country=country,
    )
    await db.commit()
    return account_repo.to_dict(account)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "DANN", "version": "1.0.0"}


# Serve frontend
import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
