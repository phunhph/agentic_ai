"""
DANN 3.0 — Integration Test.
Chạy pipeline đầy đủ: Perception → Reasoning → Execution → Critic → Learning → Output
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from v3.service import V3Service


def test_query(service: V3Service, query: str, role: str = "DEFAULT"):
    print(f"\n{'═' * 60}")
    print(f"  QUERY: {query}")
    print(f"  ROLE:  {role}")
    print(f"{'═' * 60}")

    t0 = time.time()
    result = service.run_pipeline(query, role=role)
    elapsed = time.time() - t0

    ok = result.get("ok", False)
    resp = result.get("assistant_response", "")
    data = result.get("data", [])
    reasoning = result.get("reasoning", {})

    print(f"  OK:        {ok}")
    print(f"  RESPONSE:  {resp}")
    print(f"  DATA rows: {len(data)}")
    print(f"  INTENT:    {reasoning.get('intent', '?')}")
    print(f"  ENTITY:    {reasoning.get('primary_entity', '?')}")
    print(f"  THOUGHT:   {reasoning.get('thought_process', '')[:100]}")
    print(f"  CRITIQUE:  {reasoning.get('critique', '?')}")
    print(f"  RETRIES:   {reasoning.get('retry_count', 0)}")
    print(f"  FIREWALL:  {reasoning.get('firewall_decision', '?')}")
    print(f"  LATENCY:   {reasoning.get('latency_ms', 0)}ms (wall: {elapsed:.1f}s)")
    print(f"{'─' * 60}")
    return result


def main():
    print("Initializing V3Service (DANN 3.0)...")
    service = V3Service()
    print("OK.\n")

    # Test 1: Analyze — đếm số lượng
    test_query(service, "đếm số lượng hợp đồng")

    # Test 2: Retrieve — danh sách
    test_query(service, "cho tôi xem danh sách khách hàng")

    # Test 3: Analyze — thống kê
    test_query(service, "thống kê bao nhiêu lead hiện có")

    print("\n✅ All tests completed.")


if __name__ == "__main__":
    main()
