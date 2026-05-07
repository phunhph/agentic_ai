"""
v2/agents/reasoning/agent.py
ReasoningAgent: Chịu trách nhiệm phân tích ý định, Persona, và đưa ra quyết định hành động dựa trên Neural Matrix.
"""
from pipeline.phase2_reason import reason_about_query

class ReasoningAgent:
    def __init__(self, persona: str = "DEFAULT"):
        self.persona = persona

    def execute(self, state: dict) -> dict:
        """
        Reasoning execution:
        1. Contextualize intent from IngestAgent results.
        2. Resolve Persona/Tactical strategy.
        3. Decide whether to auto-execute, clarify, or re-plan.
        """
        # Mapping logic from legacy phase2
        # In the future, this will use MCP tools to reach out to Neural Matrix
        reason_result = reason_about_query(state.get("raw_ingest", {}))
        
        return {
            "decision_state": reason_result.get("decision_state"),
            "planner_trace": reason_result.get("planner_trace_v2"),
            "tool_selection": reason_result.get("tool"),
            "should_clarify": reason_result.get("ask_clarify", False),
            "raw_reason": reason_result
        }
