from typing import List, Dict, Any, TypedDict

class AgentState(TypedDict):
    goal: str
    role: str # ADMIN hoặc BUYER
    plan: List[str]
    steps: List[Dict[str, Any]] # Chứa: thought, action, observation
    current_observation: Any
    is_finished: bool
    iteration_count: int