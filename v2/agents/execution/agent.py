"""
v2/agents/execution/agent.py
ExecutionAgent: Thực thi kế hoạch đã lên sẵn (Tool Caller).
"""
from pipeline.phase4_execute.runtime import execute_plan
from pipeline.phase4_execute.validator import validate_execution_plan

class ExecutionAgent:
    def __init__(self):
        pass

    def execute(self, state: dict) -> dict:
        """
        Execution logic:
        1. Validate the incoming plan.
        2. Run plan against the database/tools.
        3. Collect execution trace/results.
        """
        # Validate existing plan in state
        plan = state.get("planning_result", {})
        
        # Validate via legacy validator
        is_valid = validate_execution_plan(plan)
        
        if not is_valid:
            return {"status": "FAILED", "error": "Plan invalid"}
            
        # Execute plan
        results = execute_plan(plan)
        
        return {
            "status": "COMPLETED",
            "results": results,
            "execution_metadata": {"tool_used": "db_executor"}
        }
