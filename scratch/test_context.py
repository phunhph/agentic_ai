from v2.service import run_v2_pipeline
import json

def test_context():
    session_id = "test-session-123"
    print("Turn 1: Show me account Demo Account 1")
    r1 = run_v2_pipeline("chi tiết account Demo Account 1", session_id=session_id)
    print(f"Decision: {r1.get('decision_state')}")
    print(f"Layers used: {r1.get('layers', {}).get('ingest', {}).get('context_usage', {})}")
    
    print("\nTurn 2: what is its website?")
    r2 = run_v2_pipeline("website của nó là gì?", session_id=session_id)
    print(f"Decision: {r2.get('decision_state')}")
    usage = r2.get('layers', {}).get('ingest', {}).get('context_usage', {})
    print(f"Context used: {usage.get('used')}")
    print(f"Entities used: {usage.get('used_entities')}")
    
    if usage.get('used_entities'):
        print("\nSUCCESS: Context persisted!")
    else:
        print("\nFAILURE: Context lost!")

if __name__ == "__main__":
    test_context()
