from pydantic import BaseModel
from typing import Dict, Any, Optional

class AgentState(BaseModel):
    message_text: str
    sender_id: str
    intent: Optional[str] = None
    extracted_data: Dict[str, Any] = {}
    confidence_score: float = 0.0
    status_emoji: str = "⏳" # Emoji Life-cycle[cite: 3]