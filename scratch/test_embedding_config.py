import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

def test_embedding(model, version):
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:embedContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "content": {"parts": [{"text": "Hello world"}]}
    }
    print(f"Testing {version} / {model}...")
    try:
        res = requests.post(url, headers=headers, json=data, timeout=5)
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            print("SUCCESS!")
            return True
        else:
            print(f"Error: {res.text}")
    except Exception as e:
        print(f"Failed: {str(e)}")
    return False

models = ["text-embedding-004", "embedding-001"]
versions = ["v1beta", "v1"]

for v in versions:
    for m in models:
        if test_embedding(m, v):
            print(f"\nWORKING CONFIG: {v} / {m}")
            break
