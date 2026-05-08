"""
v2/agents/planning/agent.py
PlanningAgent: Chịu trách nhiệm phân tách Intent thành Task List (BabyAGI Pattern).
"""
from pipeline.phase3_plan.compiler import compile_execution_plan
from core.contracts import IngestResult, RequestFilter
import inspect

class PlanningAgent:
    def __init__(self):
        pass

    def execute(self, state: dict) -> dict:
        """
        Planning logic:
        1. Compile reasoning into structured tasks.
        2. Set up execution context for the Executor.
        """
        # Mapping legacy phase3 compiler
        raw_ingest_data = state.get("raw_ingest")
        if isinstance(raw_ingest_data, dict):
            # Extract filters if they are dictionaries
            filters_data = raw_ingest_data.get("request_filters", [])
            restored_filters = []
            for f in filters_data:
                if isinstance(f, dict):
                    restored_filters.append(RequestFilter(**f))
                else:
                    restored_filters.append(f)
            
            raw_ingest_data["request_filters"] = restored_filters
            
            # Filter only valid keys for IngestResult
            valid_keys = inspect.signature(IngestResult).parameters.keys()
            filtered_data = {k: v for k, v in raw_ingest_data.items() if k in valid_keys}
            
            # Handle potential __dict__ serialization
            ingest = IngestResult(**filtered_data)
        else:
            ingest = raw_ingest_data
        reason = state.get("raw_reason")
        
        plan = compile_execution_plan(ingest, reason)
        
        return {
            "planning_result": plan,
            "planner_mode": "auto_execution_plan"
        }
