import os
import requests
from core.config import LLM_URL, DEFAULT_MODEL


class LLMClient:
    def __init__(self, url: str = None, model: str = None):
        self.url = url or LLM_URL
        self.model = model or DEFAULT_MODEL

    def generate(self, prompt: str, chain_of_thought: bool = False, temperature: float = 0.2, timeout: int = 20):
        # If chain_of_thought is True, we append a simple instruction to encourage step-by-step reasoning.
        full_prompt = prompt
        if chain_of_thought:
            full_prompt = f"[CHAIN-OF-THOUGHT]\nPlease reason step-by-step before answering.\n\n{prompt}"

        payload = {"model": self.model, "prompt": full_prompt, "stream": False, "temperature": temperature}
        try:
            res = requests.post(self.url, json=payload, timeout=timeout)
            return res.json().get("response", "")
        except Exception as e:
            # Graceful fallback: raise to caller or return empty
            return ""
