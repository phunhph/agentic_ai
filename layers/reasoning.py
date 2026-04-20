from core.brain import call_brain

def reasoning_node(state: dict):
    # Lấy ngữ cảnh Schema từ schema.py (Phú tự định nghĩa các bảng vào đó)
    schema_info = "Tables: products, categories, inventories. Relations: category_id, product_id."
    
    ai_decision = call_brain(state["goal"], schema_info)
    
    log = {
        "block": "REASON",
        "content": ai_decision["thought"],
        "status": "THINKING"
    }
    
    return {
        "plan": [ai_decision["tool"]],
        "next_action": ai_decision["tool"],
        "next_args": ai_decision["args"],
        "node_logs": [log]
    }