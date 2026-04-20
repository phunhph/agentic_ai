import os
import json
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

# Import Framework Layers
from core.brain import agent_reasoning
from layers.perception import perception_node
from layers.action import action_node
from layers.evaluator import evaluator_node

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/run-agent")
async def run_agent(goal: str = Form(...), role: str = Form("BUYER")):
    async def event_generator():
        # KHỞI TẠO STATE (Cốt lõi của Framework)
        state = {
            "goal": goal, "role": role, "is_finished": False, 
            "iteration": 0, "observations": [], "node_logs": []
        }
        schema_context = "Tables: products(id, name, sku, price), categories(id, name), inventories(quantity)."

        while not state["is_finished"] and state["iteration"] < 3:
            state["iteration"] += 1
            
            # 1. PERCEPTION: Tiền xử lý (Xóa rác, định dạng câu hỏi)
            state.update(perception_node(state))

            # 2. REASONING: AI suy nghĩ chọn Tool
            decision = agent_reasoning(state["goal"], schema_context)
            log_r = {"block": "REASON", "content": decision["thought"], "status": "THINKING"}
            yield f"data: {json.dumps({'type': 'log', 'log': log_r}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.5)

            # 3. ACTION: Thực thi Tool đã chọn
            state["next_action"] = decision["tool"]
            state["next_args"] = decision["args"]
            a_res = action_node(state)
            state.update(a_res)
            yield f"data: {json.dumps({'type': 'log', 'log': a_res['node_logs'][0]}, ensure_ascii=False)}\n\n"

            # 4. EVALUATOR: Kiểm tra kết quả
            e_res = evaluator_node(state)
            state.update(e_res)
            if state["is_finished"]: break

        # Gửi dữ liệu cuối cùng để UI render Bảng/Card
        yield f"data: {json.dumps({'type': 'final', 'role': state['role'], 'final_result': state['observations']}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)