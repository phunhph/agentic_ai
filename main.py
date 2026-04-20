import os
import json
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from core.brain import agent_brain
from layers.perception import perception_node
from layers.action import action_node
from layers.evaluator import evaluator_node
from core.memory import AgentMemory

app = FastAPI()
memory = AgentMemory()
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/run-agent")
async def run_agent(goal: str = Form(...), role: str = Form("BUYER"), history: str = Form("[]")):
    async def event_generator():
        # Parse history
        try:
            chat_history = json.loads(history)
        except:
            chat_history = []

        # 1. PERCEPTION
        perception_result = perception_node({"goal": goal, "role": role})
        clean_goal = perception_result["goal"]
        detected_role = perception_result.get("role", role)
        
        yield f"data: {json.dumps({'type': 'log', 'log': {'block': 'PERCEIVE', 'content': f'Input: \"{clean_goal}\" | Role: {detected_role}', 'status': 'DONE'}}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.2)

        # STATE
        state = {
            "goal": clean_goal, 
            "role": detected_role, 
            "history": chat_history,
            "is_finished": False,
            "iteration": 0, 
            "steps": [], 
            "observations": []
        }

        while not state["is_finished"] and state["iteration"] < 5:
            state["iteration"] += 1
            
            # 2. PLANNING
            decision = agent_brain(state)
            thought = decision.get("thought", "...")
            tool = decision.get("tool", "error")
            args = decision.get("args", {})

            yield f"data: {json.dumps({'type': 'log', 'log': {'block': 'REASON', 'content': thought, 'status': 'THINKING'}}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)

            if tool == "final_answer":
                state["is_finished"] = True
                memory.save_experience(clean_goal, "completed", len(state["observations"]))
                yield f"data: {json.dumps({'type': 'log', 'log': {'block': 'EVAL', 'content': 'Hoàn tất mục tiêu.', 'status': 'DONE'}}, ensure_ascii=False)}\n\n"
                break
            
            if tool == "error":
                state["is_finished"] = True
                break

            # 3. EXECUTION
            state["next_action"] = tool
            state["next_args"] = args
            act_res = action_node(state)
            state["observations"] = act_res["observations"]
            
            yield f"data: {json.dumps({'type': 'log', 'log': act_res['node_logs'][0]}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)

            # 4. EVALUATOR
            eval_result = evaluator_node(state)
            state["is_finished"] = eval_result.get("is_finished", False)
            if state["is_finished"]:
                obs_count = len(state["observations"])
                yield f"data: {json.dumps({'type': 'log', 'log': {'block': 'EVAL', 'content': f'Kết quả: {obs_count} bản ghi.', 'status': 'DONE'}}, ensure_ascii=False)}\n\n"

        # FINAL RESULT
        yield f"data: {json.dumps({'type': 'final', 'role': detected_role, 'final_result': state['observations']}, ensure_ascii=False)}\n\n"


    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
