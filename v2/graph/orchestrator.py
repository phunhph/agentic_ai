"""
v2/graph/orchestrator.py
LangGraph Orchestrator: Quản lý workflow tự hành giữa các Agent.
"""
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from v2.agents.ingest.agent import IngestAgent
from v2.agents.reasoning.agent import ReasoningAgent
from v2.agents.planning.agent import PlanningAgent
from v2.agents.execution.agent import ExecutionAgent
from v2.agents.learning.agent import LearningAgent

class AgentState(TypedDict):
    query: str
    raw_ingest: dict
    raw_reason: dict
    planning_result: dict
    execution_result: dict
    learning_result: dict

def create_orchestrator():
    workflow = StateGraph(AgentState)

    # Khởi tạo các Agent
    ingest_agent = IngestAgent()
    reason_agent = ReasoningAgent()
    plan_agent = PlanningAgent()
    exec_agent = ExecutionAgent()
    learn_agent = LearningAgent()

    # Thêm các Node vào Graph
    workflow.add_node("ingest", ingest_agent.execute)
    workflow.add_node("reason", reason_agent.execute)
    workflow.add_node("plan", plan_agent.execute)
    workflow.add_node("execute", exec_agent.execute)
    workflow.add_node("learn", learn_agent.execute)

    # Cấu trúc luồng (Edges)
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "reason")
    workflow.add_edge("reason", "plan")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "learn")
    workflow.add_edge("learn", END)

    return workflow.compile()
