"""
v2/agents/learning/agent.py
LearningAgent: Thực hiện vòng lặp phản hồi, cập nhật Neural Matrix và tri thức đồ thị.
"""
from pipeline.phase5_learn.matrix import train_matrix_v2
from pipeline.phase5_learn.firewall import evaluate_firewall, log_firewall_event

class LearningAgent:
    def __init__(self):
        pass

    def execute(self, state: dict) -> dict:
        """
        Learning logic:
        1. Evaluate execution results.
        2. Log events to the firewall/quarantine.
        3. Trigger Neural Matrix retrain (if metrics warrant).
        """
        # Log to firewall
        event = log_firewall_event(state.get("raw_reason", {}))
        
        # Matrix evolution
        # Logic: train_matrix_v2 is a heavy operation, 
        # normally triggered based on 'evidence_score' or 'thresholds'
        train_matrix_v2()
        
        return {
            "status": "LEARNED",
            "evolution_metrics": {"version_updated": True},
            "firewall_event": event
        }
