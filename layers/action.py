from tools.inventory_tool import search_products, get_inventory_stats

def action_node(state: dict):
    tool = state.get("next_action")
    args = state.get("next_args", {})
    results = []

    if tool == "search_products":
        results = search_products(args.get("keyword", ""))
    elif tool == "get_inventory_stats":
        results = get_inventory_stats()

    return {
        "observations": results,
        "node_logs": [{
            "block": "ACT", 
            "content": f"Đã thực thi công cụ '{tool}' trên Postgres.", 
            "status": "SUCCESS" if results else "EMPTY"
        }]
    }