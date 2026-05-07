"""
v2/agents/ingest/agent.py
IngestAgent: Chịu trách nhiệm tiếp nhận và chuẩn hóa truy vấn đầu vào.
"""
from pipeline.phase1_ingest.parser import ingest_query
from v2.intelligence.resolver import DynamicIntentResolver

class IngestAgent:
    def __init__(self, role: str = "DEFAULT"):
        self.role = role

    def execute(self, state: dict) -> dict:
        """
        Processing entry point:
        1. Parse raw query.
        2. Resolve dynamic intent/context.
        3. Update state.
        """
        query = state.get("query", "")
        
        # Parse query using established logic
        ingest_result = ingest_query(query, role=self.role)
        
        # Dynamic Resolution
        is_follow_up = DynamicIntentResolver.is_follow_up(query, state.get("session_context", {})) > 0.5
        
        return {
            "intent": ingest_result.intent,
            "entities": ingest_result.entities,
            "ambiguity_score": ingest_result.ambiguity_score,
            "is_follow_up": is_follow_up,
            "raw_ingest": ingest_result.__dict__
        }
