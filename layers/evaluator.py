def evaluator_node(state: dict):
    results = state.get("observations", [])
    iteration = state.get("iteration", 0)
    
    if results or iteration >= 3:
        return {"is_finished": True}
    
    return {"is_finished": False}