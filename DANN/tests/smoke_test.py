"""Smoke test for DANN system — verify core components work."""
import sys
import json


def test_imports():
    """Test all critical imports."""
    print("Testing imports...")
    try:
        from core.config import DATABASE_URL, LLM_URL
        from core.database import SessionLocal, Base
        from core.state import get_state
        from core.llm import LLMClient
        from core.memory import VectorMemory
        from core.reasoning import ReasoningLoops
        from core.langgraph import LangGraphClient, build_extraction_spec
        from core.orchestrator import Orchestrator
        from agents.router import RouterAgent
        from agents.analyst import AnalystAgent
        from agents.operator import OperatorAgent
        from agents.tactician import TacticianAgent
        from ui.card_builder import build_success_card_v2, build_fallback_card_v2, build_emoji_status_card
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_orchestrator():
    """Test orchestrator with sample message."""
    print("\nTesting Orchestrator...")
    try:
        from core.orchestrator import Orchestrator
        orchestrator = Orchestrator()
        
        # Test UPDATE intent
        msg = "Tạo deal Acme giá $50k, cần budget approval từ CFO"
        result = orchestrator.run(msg, "test_user")
        
        print(f"  Input: {msg}")
        print(f"  Result type: {type(result)}")
        if isinstance(result, dict):
            print(f"  Result keys: {list(result.keys())}")
        print("✅ Orchestrator test passed")
        return True
    except Exception as e:
        print(f"❌ Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_card_builders():
    """Test card builder functions."""
    print("\nTesting Card Builders...")
    try:
        from ui.card_builder import (build_success_card_v2, build_fallback_card_v2, 
                                      build_emoji_status_card, build_query_result_card_v2)
        
        # Test success card
        data = {"name": "Acme Deal", "budget": 50000, "status": "Following", "bant_need": "CRM integration"}
        card = build_success_card_v2(data)
        assert "cardsV2" in card
        print("✅ Success card: OK")
        
        # Test fallback card
        card = build_fallback_card_v2("Status", ["Following", "RFP", "Won"])
        assert "cardsV2" in card
        print("✅ Fallback card: OK")
        
        # Test status card
        card = build_emoji_status_card("⏳", "Processing your request...")
        assert "cardsV2" in card
        print("✅ Status card: OK")
        
        # Test query result card
        results = [{"name": "Contact A", "email": "a@acme.com"}, {"name": "Contact B", "email": "b@acme.com"}]
        card = build_query_result_card_v2("contacts", results)
        assert "cardsV2" in card
        print("✅ Query card: OK")
        
        print("✅ Card builders test passed")
        return True
    except Exception as e:
        print(f"❌ Card builders test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_store():
    """Test state store for Q&A and trace."""
    print("\nTesting State Store...")
    try:
        from core.state import get_state
        state = get_state()
        
        # Add Q&A
        state.add_qna("Test message", "test_sender")
        qna = state.get_qna()
        assert len(qna) > 0
        assert qna[-1]["message"] == "Test message"
        print("✅ Q&A store: OK")
        
        # Add trace
        state.add_trace("test_source", "info", "test message")
        trace = state.get_trace()
        assert len(trace) > 0
        print("✅ Trace store: OK")
        
        print("✅ State store test passed")
        return True
    except Exception as e:
        print(f"❌ State store test failed: {e}")
        return False


def test_memory():
    """Test vector memory."""
    print("\nTesting Vector Memory...")
    try:
        from core.memory import VectorMemory
        mem = VectorMemory()
        
        # Add items
        mem.add("Deal with Acme Corp", {"source": "chat"})
        mem.add("Budget approval needed", {"source": "chat"})
        
        # Query
        results = mem.query("Acme", top_k=2)
        assert len(results) > 0
        print(f"✅ Memory query returned {len(results)} results")
        
        print("✅ Vector memory test passed")
        return True
    except Exception as e:
        print(f"❌ Vector memory test failed: {e}")
        return False


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("DANN SYSTEM SMOKE TEST")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_card_builders,
        test_state_store,
        test_memory,
        test_orchestrator,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)
    
    return all(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
