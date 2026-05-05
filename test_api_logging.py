#!/usr/bin/env python3
"""
Test script to verify API client logging.
Shows all debug, info, and error logs from API calls.
"""
import logging
import sys

# Configure logging to show all levels
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)-8s] %(name)s: %(message)s',
    stream=sys.stdout
)

from v2.api_clients import APIClient, get_dynamic_client

def test_client_selection():
    """Test dynamic client selection with logging."""
    print("\n" + "="*60)
    print("TEST 1: Dynamic Client Selection")
    print("="*60 + "\n")
    
    for i in range(3):
        print(f"\nAttempt {i+1}:")
        client = get_dynamic_client("parse")
        print(f"Selected model: {client.model_type}")

def test_json_response_validation():
    """Test JSON response validation with mock responses."""
    print("\n" + "="*60)
    print("TEST 2: JSON Response Validation")
    print("="*60 + "\n")
    
    client = APIClient("grok")
    
    test_cases = [
        ("Valid JSON", '{"intent": "retrieve", "entities": ["account"]}'),
        ("JSON in markdown", '```json\n{"intent": "retrieve", "entities": ["contact"]}\n```'),
        ("Invalid JSON", 'This is not JSON'),
        ("Empty response", ''),
    ]
    
    for label, response_text in test_cases:
        print(f"\n--- {label} ---")
        response = {"response": response_text}
        result = client._ensure_json_response(response)
        print(f"Input: {response_text[:60]}...")
        print(f"Output: {result['response'][:80]}...")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("API CLIENT LOGGING TEST SUITE")
    print("="*60)
    
    test_client_selection()
    test_json_response_validation()
    
    print("\n" + "="*60)
    print("✓ All tests completed")
    print("="*60 + "\n")
