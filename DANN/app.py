from fastapi import FastAPI, Request
from agents.router import RouterAgent
from agents.analyst import AnalystAgent
from agents.operator import OperatorAgent
from core.orchestrator import Orchestrator
from ui.success_card import build_success_card
from fastapi.responses import HTMLResponse, JSONResponse
from core.state import get_state

app = FastAPI()
router = RouterAgent()
analyst = AnalystAgent()
operator = OperatorAgent()
orchestrator = Orchestrator()
state = get_state()

@app.post("/google-chat")
async def handle_event(request: Request):
    event = await request.json()
    msg = event.get("message", {}).get("text", "")
    
    # State 1: ⏳ (Nhận diện intent)
    intent = router.classify(msg)
    
    if intent == "UPDATE":
        # State 2: 📊 (Phân tích dữ liệu)[cite: 3]
        extracted_data = analyst.extract_and_map(msg)
        
        # State 3: 🛠️ (Ghi vào CSDL)[cite: 3]
        success = operator.process_update(extracted_data)
        
        if success:
            # State 4: ✅ (Trả về Card kết quả)[cite: 3]
            return build_success_card(extracted_data)
            
    return {"text": "Bot đã nhận thông tin nhưng chưa thể phân loại hành động."}


@app.get('/ui/qna', response_class=HTMLResponse)
async def qna_ui():
    html = open('ui/qna.html', encoding='utf-8').read()
    return HTMLResponse(content=html)


@app.get('/ui/trace', response_class=HTMLResponse)
async def trace_ui():
    html = open('ui/trace.html', encoding='utf-8').read()
    return HTMLResponse(content=html)


@app.get('/api/qna')
async def api_qna():
    return JSONResponse(content=state.get_qna())


@app.get('/api/trace')
async def api_trace():
    return JSONResponse(content=state.get_trace())


# app.py (Dòng 69 trở đi)
@app.post("/api/send")
async def handle_request(request: Request):
    data = await request.json()
    message = data.get('message', '')
    sender = data.get('sender', 'web')

    # Gọi hàm run (đã sửa thành async ở trên)
    response_data = await orchestrator.run(message, sender) 
    
    # SỬA LẠI PHẦN RETURN: Chỉ lấy giá trị text để hiện lên box chat
    if isinstance(response_data, dict):
        clean_text = response_data.get('message', str(response_data))
    else:
        clean_text = str(response_data)

    return {
        "message": clean_text, 
        "sender": "Agent"
    }