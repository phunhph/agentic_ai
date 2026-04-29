from agents.router import RouterAgent
from agents.analyst import AnalystAgent
from agents.operator import OperatorAgent
from agents.tactician import TacticianAgent
from ui.success_card import build_success_card
from models.schema import AgentState
from core.state import get_state


class Orchestrator:
    def __init__(self):
        self.router = RouterAgent()
        self.analyst = AnalystAgent()
        self.operator = OperatorAgent()
        self.tactician = TacticianAgent()
        self.state = get_state()

    async def run(self, message: str, sender_id: str):
        """Asynchronous orchestrator run."""
        state = AgentState(message_text=message, sender_id=sender_id)
        state.status_emoji = "⏳"
        print(f"Status: ⏳ (Ghi nhận tin nhắn từ {sender_id})")
        try:
            self.state.add_qna(message, sender_id)
        except Exception:
            pass

        state.intent = self.router.classify(message)
        state.status_emoji = "📊"
        print(f"Status: 📊 (Phân loại intent: {state.intent})")
        try:
            self.state.add_trace('router', 'info', f"intent={state.intent}")
        except Exception:
            pass

        if state.intent == "UPDATE":
            state.status_emoji = "🛠️"
            extracted = self.analyst.extract_and_map(message)
            state.extracted_data = extracted
            state.confidence_score = 0.8  # placeholder
            print("Status: 🛠️ (Đang trích xuất BANT và chuẩn bị ghi vào DB)")
            try:
                self.state.add_trace('analyst', 'info', 'extracted', payload=extracted)
            except Exception:
                pass

            success = self.operator.process_update(extracted)
            if not success:
                state.status_emoji = "⚠️"
                print("Status: ⚠️ (Ghi vào DB thất bại)")
                try:
                    self.state.add_trace('operator', 'error', 'db_write_failed')
                except Exception:
                    pass
                return {"text": "Có lỗi khi ghi dữ liệu."}

            suggestions = self.tactician.suggest_actions(extracted)
            extracted['tactics'] = suggestions
            try:
                self.state.add_trace('tactician', 'info', 'suggestions', payload={'suggestions': suggestions})
            except Exception:
                pass

            state.status_emoji = "✅"
            print("Status: ✅ (Đã cập nhật CRM thành công)")
            return build_success_card(extracted)

        state.status_emoji = "❓"
        return {"text": "Bot đã nhận thông tin nhưng chưa thể phân loại hành động."}