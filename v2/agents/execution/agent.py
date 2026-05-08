"""
v2/agents/execution/agent.py
ExecutionAgent: Thực thi kế hoạch đã lên sẵn (Tool Caller).
"""
from dataclasses import asdict
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
        validation = validate_execution_plan(plan)
        if not validation.ok:
            return {
                "status": "FAILED",
                "record_count": 0,
                "results": [],
                "errors": validation.errors,
                "execution_trace": {
                    "guardrail": {"ok": False, "errors": validation.errors, "warnings": validation.warnings}
                }
            }

        execution_result = execute_plan(plan)
        results_data = []
        if hasattr(execution_result, "data") and isinstance(execution_result.data, list):
            results_data = execution_result.data

        execution_trace = execution_result.execution_trace if isinstance(execution_result.execution_trace, dict) else {}
        return {
            "execution_result": {
                "status": "EXECUTED",
                "record_count": len(results_data),
                "results": results_data,
                "errors": [] if execution_result.success else ["execution_failed"],
                "execution_trace": execution_trace,
                "execution_metadata": {"tool_used": "db_executor"}
            }
        }
