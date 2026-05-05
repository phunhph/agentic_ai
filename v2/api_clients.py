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
            print(f"✓ Đã nạp {key_name}: {key_preview}")
        elif key_value:
            print(f"⚠ {key_name} quá ngắn (có thể không hợp lệ): {len(key_value)} ký tự")
        else:
            print(f"✗ {key_name} TRỐNG hoặc CHƯA ĐƯỢC NẠP")

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
    
    def _ensure_json_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure response contains valid JSON. Extract JSON from text if needed."""
        content = response.get("response", "")
        if not content:
            print("Lỗi: Phản hồi từ model trống")
            return {"response": json.dumps({"error": "Empty response from model"})}
        
        # Try to parse as JSON first
        try:
            json.loads(content)
            print("Phản hồi đã là JSON hợp lệ")
            return response  # Already valid JSON
        except json.JSONDecodeError:
            print("Phản hồi không phải JSON, đang thử trích xuất...")
            pass
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                extracted = json_match.group(1).strip()
                json.loads(extracted)  # Validate
                print("Đã trích xuất JSON thành công từ markdown code block")
                return {"response": extracted}
            except json.JSONDecodeError:
                print("Nội dung trích xuất từ markdown không phải JSON hợp lệ")
                pass
        
        # Try to find JSON object/array in the content
        for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', content):
            try:
                extracted = match.group(0)
                json.loads(extracted)  # Validate
                print(f"Đã trích xuất JSON thành công (độ dài: {len(extracted)})")
                return {"response": extracted}
            except json.JSONDecodeError:
                print("Ứng viên trích xuất không phải JSON, đang thử tiếp...")
                pass
        
        # If no valid JSON found, return error
        print(f"Thất bại khi trích xuất JSON. Xem trước nội dung thô: {content[:200]}")
        response.update({"response": json.dumps({"error": "Model did not return valid JSON", "raw": content[:500]})})
        return response

    def _call_groq(self, prompt: str, format: str) -> Dict[str, Any]:
        print(f"Đang gọi Groq API (định dạng={format})")
        print(f"Xem trước Prompt: {prompt[:100]}...")
        
        # Log API key status
        if not GROK_API_KEY:
            print("✗ GROQ_API_KEY trống hoặc chưa được nạp!")
            return {"response": json.dumps({"error": "Groq API key not configured"})}
        
        if len(GROK_API_KEY) < 10:
            print(f"✗ GROQ_API_KEY quá ngắn ({len(GROK_API_KEY)} ký tự), có vẻ không hợp lệ")
            return {"response": json.dumps({"error": "Groq API key appears invalid"})}
        
        print(f"Đang dùng Groq API key: {GROK_API_KEY[:5]}...{GROK_API_KEY[-5:]}")
        
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
            print(f"✓ Gọi Groq API thành công (độ dài phản hồi: {len(content)})")
            print(f"Xem trước phản hồi: {content[:150]}...")
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
            print("✗ Groq API bị quá hạn (timeout) sau 30 giây")
            return {"response": json.dumps({"error": "Groq API timeout"})}
        except requests.exceptions.HTTPError as e:
            print(f"✗ Lỗi HTTP Groq API: {e.response.status_code} - {e.response.text[:200]}")
            return {"response": json.dumps({"error": f"Groq API HTTP error: {e.response.status_code}"})}
        except requests.exceptions.RequestException as e:
            print(f"✗ Lỗi Groq API: {str(e)}")
            return {"response": json.dumps({"error": f"Groq API error: {str(e)}"})}

    def _call_gemini(self, prompt: str, format: str) -> Dict[str, Any]:
        """Call Gemini API via REST endpoint to avoid async client cleanup issues"""
        print(f"Đang gọi Gemini API (định dạng={format})")
        print(f"Xem trước Prompt: {prompt[:100]}...")
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        # Log API key status
        if not GEMINI_API_KEY:
            print("✗ GEMINI_API_KEY trống hoặc chưa được nạp!")
            return {"response": json.dumps({"error": "Gemini API key not configured"})}
        
        if len(GEMINI_API_KEY) < 10:
            print(f"✗ GEMINI_API_KEY quá ngắn ({len(GEMINI_API_KEY)} ký tự), có vẻ không hợp lệ")
            return {"response": json.dumps({"error": "Gemini API key appears invalid"})}
        
        print(f"Đang dùng Gemini API key: {GEMINI_API_KEY[:5]}...{GEMINI_API_KEY[-5:]}")
        
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
                print("✗ Gemini API trả về nội dung trống")
                content = json.dumps({"error": "Empty response from Gemini"})
            else:
                print(f"✓ Gọi Gemini API thành công (độ dài phản hồi: {len(content)})")
                print(f"Xem trước phản hồi: {content[:150]}...")
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
            print("✗ Gemini API bị quá hạn (timeout) sau 30 giây")
            return {"response": json.dumps({"error": "Gemini API timeout"})}
        except requests.exceptions.HTTPError as e:
            print(f"✗ Lỗi HTTP Gemini API: {e.response.status_code} - {e.response.text[:200]}")
            return {"response": json.dumps({"error": f"Gemini API HTTP error: {e.response.status_code}"})}
        except requests.exceptions.RequestException as e:
            print(f"✗ Lỗi Gemini API: {str(e)}")
            return {"response": json.dumps({"error": f"Gemini API error: {str(e)}"})}

    def _call_openrouter(self, prompt: str, format: str) -> Dict[str, Any]:
        print(f"Đang gọi OpenRouter API (định dạng={format})")
        print(f"Xem trước Prompt: {prompt[:100]}...")
        
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
            print(f"✓ Gọi OpenRouter API thành công (độ dài phản hồi: {len(content)})")
            print(f"Xem trước phản hồi: {content[:150]}...")
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
            print("✗ OpenRouter API bị quá hạn (timeout) sau 30 giây")
            return {"response": json.dumps({"error": "OpenRouter API timeout"})}
        except requests.exceptions.RequestException as e:
            print(f"✗ Lỗi OpenRouter API: {str(e)}")
            return {"response": json.dumps({"error": f"OpenRouter API error: {str(e)}"})}

# Model selection based on settings
def get_dynamic_client(task_type: str = "chat") -> APIClient:
    """Get the configured API client from settings."""
    selected = CHAT_MODEL or "grok"
    print(f"Using {selected} API client (configured in settings) for task type: {task_type}")
    return APIClient(selected)