"""
v2/agents/planning/agent.py
PlanningAgent: Chịu trách nhiệm phân tách Intent thành Task List (BabyAGI Pattern).
"""
from pipeline.phase3_plan.compiler import compile_execution_plan

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
        ingest = state.get("raw_ingest")
        reason = state.get("raw_reason")
        
        plan = compile_execution_plan(ingest, reason)
        
        return {
            "root_table": plan.root_table,
            "join_path": plan.join_path,
            "tasks": plan.where_filters, # Or more structured task list
            "planner_mode": "auto_execution_plan"
        }
