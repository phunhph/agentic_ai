"""
DANN - Short-Term Memory System
In-memory conversation context using a sliding window.
Stores recent messages per sender/space for debouncing and context.
"""
import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MessageBuffer:
    """Debounce buffer: collects burst messages from same sender"""
    sender_id: str
    space_id: str
    messages: list[str] = field(default_factory=list)
    last_received: float = field(default_factory=time.time)
    timer_task: Optional[asyncio.Task] = None


@dataclass
class ConversationTurn:
    role: str  # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    intent: Optional[str] = None
    card_type: Optional[str] = None


class ShortTermMemory:
    """
    Manages per-sender conversation windows.
    - Debounce: Groups burst messages within DEBOUNCE_SECONDS
    - Context window: Keeps last N turns per sender
    - Processing state: Tracks emoji lifecycle per message
    """

    DEBOUNCE_SECONDS = 5.0
    MAX_TURNS = 10  # Last 10 conversation turns per sender

    def __init__(self):
        self._conversations: dict[str, deque[ConversationTurn]] = defaultdict(
            lambda: deque(maxlen=self.MAX_TURNS)
        )
        self._buffers: dict[str, MessageBuffer] = {}
        self._processing_states: dict[str, str] = {}  # message_id -> emoji state
        self._lock = asyncio.Lock()

    def _key(self, sender_id: str, space_id: str) -> str:
        return f"{space_id}::{sender_id}"

    async def buffer_message(
        self,
        sender_id: str,
        space_id: str,
        text: str,
        callback,  # Called with merged text after debounce
    ) -> None:
        """Debounce: accumulate messages, fire callback after silence"""
        key = self._key(sender_id, space_id)

        async with self._lock:
            buf = self._buffers.get(key)
            if buf:
                buf.messages.append(text)
                buf.last_received = time.time()
                if buf.timer_task and not buf.timer_task.done():
                    buf.timer_task.cancel()
            else:
                buf = MessageBuffer(sender_id=sender_id, space_id=space_id, messages=[text])
                self._buffers[key] = buf

            async def fire():
                await asyncio.sleep(self.DEBOUNCE_SECONDS)
                async with self._lock:
                    b = self._buffers.pop(key, None)
                if b:
                    merged = " ".join(b.messages)
                    await callback(merged)

            buf.timer_task = asyncio.create_task(fire())

    async def buffer_immediate(
        self,
        sender_id: str,
        space_id: str,
        text: str,
        callback,
    ) -> None:
        """@mention: process immediately, no debounce"""
        key = self._key(sender_id, space_id)
        async with self._lock:
            buf = self._buffers.pop(key, None)
            if buf and buf.timer_task:
                buf.timer_task.cancel()
        await callback(text)

    def add_turn(self, sender_id: str, space_id: str, role: str, content: str,
                 intent: Optional[str] = None, card_type: Optional[str] = None):
        key = self._key(sender_id, space_id)
        self._conversations[key].append(
            ConversationTurn(role=role, content=content, intent=intent, card_type=card_type)
        )

    def get_history(self, sender_id: str, space_id: str) -> list[ConversationTurn]:
        key = self._key(sender_id, space_id)
        return list(self._conversations[key])

    def get_langchain_messages(self, sender_id: str, space_id: str) -> list[dict]:
        """Format for LangChain/LangGraph message format"""
        turns = self.get_history(sender_id, space_id)
        return [
            {"role": "user" if t.role == "user" else "assistant", "content": t.content}
            for t in turns
        ]

    def set_processing_state(self, message_id: str, state: str):
        """Emoji State Machine: queued | analyzing | processing | done | error | ambiguous"""
        self._processing_states[message_id] = state

    def get_processing_state(self, message_id: str) -> Optional[str]:
        return self._processing_states.get(message_id)

    def clear_sender(self, sender_id: str, space_id: str):
        key = self._key(sender_id, space_id)
        self._conversations.pop(key, None)
        self._buffers.pop(key, None)


# Singleton instance
short_term_memory = ShortTermMemory()
