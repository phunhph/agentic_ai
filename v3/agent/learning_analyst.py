from __future__ import annotations
import json
from pathlib import Path
from v2.learn.trainset import append_trainset_sample

class LearningAnalyst:
    """
    The "Brain" for Continuous Learning.
    Analyzes user corrections and updates the system's knowledge base.
    """
    
    def __init__(self):
        pass

    def learn_from_correction(self, raw_query: str, corrected_plan: dict, notes: str = "") -> dict:
        """
        Manually trigger a 'Lesson Learned' from a user correction.
        """
        sample = {
            "normalized_query": raw_query.strip().lower(),
            "intent": corrected_plan.get("intent", "retrieve"),
            "root_table": corrected_plan.get("primary_entity"),
            "entities": corrected_plan.get("entities", []),
            "filters": corrected_plan.get("filters", []),
            "join_plan": corrected_plan.get("join_plan", []),
            "success_label": True,
            "source": "user_correction",
            "notes": notes
        }
        
        result = append_trainset_sample(sample)
        return result

    def analyze_feedback_chain(self, history: list[dict]) -> dict | None:
        """
        Automatically detect if the user is correcting the AI in a conversation.
        If a correction pattern is found, suggest a learning update.
        """
        if len(history) < 2:
            return None
            
        last_user_msg = history[-1].get("content", "").lower()
        correction_keywords = ["không phải", "sai rồi", "nhầm rồi", "ý tôi là", "phải là", "not this", "wrong"]
        
        if any(k in last_user_msg for k in correction_keywords):
            # Potential correction detected. 
            # In a real system, we might trigger an LLM call to extract the corrected intent.
            return {"type": "correction_signal", "msg": last_user_msg}
            
        return None
