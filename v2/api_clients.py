import json
import requests
import re
from typing import Dict, Any
from infra.settings import GROK_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, CHAT_MODEL



# Validate API keys on import
def _validate_api_keys():
    """Check if API keys are properly loaded."""
    keys_info = [
        ("GROK_API_KEY", GROK_API_KEY),
        ("GEMINI_API_KEY", GEMINI_API_KEY),
        ("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    ]
    
    for key_name, key_value in keys_info:
        if key_value and len(key_value) > 10:
            # Mask the actual key for security
            key_preview = f"{key_value[:5]}...{key_value[-5:]}"
            print(f"[OK] Load {key_name}: {key_preview}")
        elif key_value:
            print(f"[WARN] {key_name} too short: {len(key_value)} chars")
        else:
            print(f"[ERR] {key_name} EMPTY")

_validate_api_keys()

class APIClient:
    def __init__(self, model_type: str):
        self.model_type = model_type

    def generate(self, prompt: str, format: str = "json") -> Dict[str, Any]:
        """Generate response from API. If format='json', ensures valid JSON is returned."""
        if self.model_type in ["grok", "groq"]:
            response = self._call_groq(prompt, format)
        elif self.model_type == "gemini":
            response = self._call_gemini(prompt, format)
        elif self.model_type == "openrouter":
            response = self._call_openrouter(prompt, format)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
        
        # If JSON format was requested, validate and extract JSON
        if format == "json":
            return self._ensure_json_response(response)
        return response
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for the given text."""
        # We prefer Gemini for embeddings as it's highly reliable
        return self._call_gemini_embedding(text)

    def _ensure_json_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure response contains valid JSON. Extract JSON from text if needed."""
        content = response.get("response", "")
        if not content:
            print("Error: Model response is empty")
            return {"response": json.dumps({"error": "Empty response from model"})}
        
        # Try to parse as JSON first
        try:
            json.loads(content)
            print("Response is already valid JSON")
            return response  # Already valid JSON
        except json.JSONDecodeError:
            print("Response is not JSON, trying to extract...")
            pass
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                extracted = json_match.group(1).strip()
                json.loads(extracted)  # Validate
                print("Successfully extracted JSON from markdown code block")
                return {"response": extracted}
            except json.JSONDecodeError:
                print("Extracted content from markdown is not valid JSON")
                pass
        
        # Try to find JSON object/array in the content
        for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', content):
            try:
                extracted = match.group(0)
                json.loads(extracted)  # Validate
                print(f"Successfully extracted JSON (length: {len(extracted)})")
                return {"response": extracted}
            except json.JSONDecodeError:
                print("Candidate extraction is not JSON, trying next...")
                pass
        
        # If no valid JSON found, return error
        print(f"Failed to extract JSON. Raw content preview: {content[:200]}")
        response.update({"response": json.dumps({"error": "Model did not return valid JSON", "raw": content[:500]})})
        return response

    def _call_groq(self, prompt: str, format: str) -> Dict[str, Any]:
        print(f"Calling Groq API (format={format})")
        # Do not print preview if format=text as it may contain Unicode
        if format != "text":
            print(f"Prompt preview: {prompt[:100]}...")
        
        # Log API key status
        if not GROK_API_KEY:
            print("[ERR] GROQ_API_KEY is empty!")
            return {"response": json.dumps({"error": "Groq API key not configured"})}
        
        if len(GROK_API_KEY) < 10:
            print(f"[ERR] GROQ_API_KEY too short ({len(GROK_API_KEY)} chars)")
            return {"response": json.dumps({"error": "Groq API key appears invalid"})}
        
        print(f"Using Groq API key: {GROK_API_KEY[:5]}...{GROK_API_KEY[-5:]}")
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }
        adjusted_prompt = prompt
        if format == "json":
            adjusted_prompt = prompt + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no code blocks. Just raw JSON."
        
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": adjusted_prompt}],
            "max_tokens": 2000,
            "temperature": 0.1
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"[OK] Groq API success (response length: {len(content)})")
            # Avoid printing response preview if it contains Unicode on Windows
            return {
                "response": content,
                "llm_trace": {
                    "model": data["model"],
                    "prompt": prompt,
                    "response": content,
                    "usage": result.get("usage", {})
                }
            }
        except requests.exceptions.Timeout:
            print("[ERR] Groq API timeout after 30s")
            return {"response": json.dumps({"error": "Groq API timeout"})}
        except requests.exceptions.HTTPError as e:
            print(f"[ERR] Groq API HTTP error: {e.response.status_code}")
            return {"response": json.dumps({"error": f"Groq API HTTP error: {e.response.status_code}"})}
        except requests.exceptions.RequestException as e:
            print(f"[ERR] Groq API error: {str(e)}")
            return {"response": json.dumps({"error": f"Groq API error: {str(e)}"})}

    def _call_gemini(self, prompt: str, format: str) -> Dict[str, Any]:
        """Call Gemini API via REST endpoint to avoid async client cleanup issues"""
        print(f"Calling Gemini API (format={format})")
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        # Log API key status
        if not GEMINI_API_KEY:
            print("[ERR] GEMINI_API_KEY is empty!")
            return {"response": json.dumps({"error": "Gemini API key not configured"})}
        
        if len(GEMINI_API_KEY) < 10:
            print(f"[ERR] GEMINI_API_KEY too short ({len(GEMINI_API_KEY)} chars)")
            return {"response": json.dumps({"error": "Gemini API key appears invalid"})}
        
        print(f"Using Gemini API key: {GEMINI_API_KEY[:5]}...{GEMINI_API_KEY[-5:]}")
        
        headers = {
            "Content-Type": "application/json",
        }
        params = {"key": GEMINI_API_KEY}
        
        adjusted_prompt = prompt
        if format == "json":
            adjusted_prompt = prompt + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no code blocks. Just raw JSON."
        
        data = {
            "contents": [{"parts": [{"text": adjusted_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 2000,
                "temperature": 0.1
            }
        }
        try:
            response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            # Extract text from Gemini API response structure
            content = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not content:
                print("[ERR] Gemini API returned empty content")
                content = json.dumps({"error": "Empty response from Gemini"})
            else:
                print(f"[OK] Gemini API success (response length: {len(content)})")
            return {
                "response": content,
                "llm_trace": {
                    "model": "gemini-1.5-flash",
                    "prompt": prompt,
                    "response": content,
                    "usage": result.get("usageMetadata", {})
                }
            }
        except requests.exceptions.Timeout:
            print("[ERR] Gemini API timeout after 30s")
            return {"response": json.dumps({"error": "Gemini API timeout"})}
        except requests.exceptions.HTTPError as e:
            print(f"[ERR] Gemini API HTTP error: {e.response.status_code}")
            return {"response": json.dumps({"error": f"Gemini API HTTP error: {e.response.status_code}"})}
        except requests.exceptions.RequestException as e:
            print(f"[ERR] Gemini API error: {str(e)}")
            return {"response": json.dumps({"error": f"Gemini API error: {str(e)}"})}

    def _call_gemini_embedding(self, text: str) -> list[float]:
        """Call Gemini Embedding API with fallback"""
        if not GEMINI_API_KEY:
            print("[ERR] GEMINI_API_KEY is empty, cannot get embedding")
            return []
            
        # Try gemini-embedding-2 first, then fallback to gemini-embedding-001
        models = ["gemini-embedding-2", "gemini-embedding-001"]
        headers = {"Content-Type": "application/json"}
        params = {"key": GEMINI_API_KEY}
        
        for model_name in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent"
            data = {
                "content": {"parts": [{"text": text}]}
            }
            try:
                print(f"Trying Gemini Embedding with {model_name}...")
                response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    embedding = result.get("embedding", {}).get("values", [])
                    print(f"[OK] Embedding success with {model_name} (size: {len(embedding)})")
                    return embedding
                else:
                    print(f"[WARN] {model_name} failed with status {response.status_code}")
            except Exception as e:
                print(f"[WARN] Error calling {model_name}: {str(e)}")
                
        print("[ERR] All Gemini Embedding attempts failed")
        return []

    def _call_openrouter(self, prompt: str, format: str) -> Dict[str, Any]:
        print(f"Calling OpenRouter API (format={format})")
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        adjusted_prompt = prompt
        if format == "json":
            adjusted_prompt = prompt + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no code blocks. Just raw JSON."
        
        data = {
            "model": "google/gemma-3-12b",
            "messages": [{"role": "user", "content": adjusted_prompt}],
            "max_tokens": 2000,
            "temperature": 0.1
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"[OK] OpenRouter API success (response length: {len(content)})")
            return {
                "response": content,
                "llm_trace": {
                    "model": data["model"],
                    "prompt": prompt,
                    "response": content,
                    "usage": result.get("usage", {})
                }
            }
        except requests.exceptions.Timeout:
            print("[ERR] OpenRouter API timeout after 30s")
            return {"response": json.dumps({"error": "OpenRouter API timeout"})}
        except requests.exceptions.RequestException as e:
            print(f"[ERR] OpenRouter API error: {str(e)}")
            return {"response": json.dumps({"error": f"OpenRouter API error: {str(e)}"})}

# Model selection based on settings
def get_dynamic_client(task_type: str = "chat") -> APIClient:
    """Get the configured API client from settings."""
    if task_type == "embedding":
        # Force gemini for embedding if available
        if GEMINI_API_KEY:
            return APIClient("gemini")
            
    selected = CHAT_MODEL or "grok"
    print(f"Using {selected} API client (configured in settings) for task type: {task_type}")
    return APIClient(selected)