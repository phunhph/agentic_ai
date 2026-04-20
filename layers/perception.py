def perception_node(state: dict):
    raw_goal = state.get("goal", "").strip()
    clean_goal = " ".join(raw_goal.split())
    
    return {
        "goal": clean_goal,
        "status": "INPUT_NORMALIZED"
    }