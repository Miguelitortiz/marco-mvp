"""Safe LLM adapters. Network clients are imported only when used."""
import os
from typing import Any


class MockLLMAdapter:
    def __init__(self, response: str = "Borrador determinista basado en la evidencia.") -> None:
        self.response = response
        self.calls: list[tuple[str, int]] = []

    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        self.calls.append((prompt, max_tokens))
        return " ".join(self.response.split()[:max_tokens])


class OpenAIAdapter:
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        self.model, self.api_key = model, api_key or os.getenv("OPENAI_API_KEY")

    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY no está configurada; use MockLLMAdapter.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Instale el extra opcional 'openai' para usar OpenAIAdapter.") from exc
        client = OpenAI(api_key=self.api_key)
        result: Any = client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return result.choices[0].message.content or ""


class OllamaAdapter:
    def __init__(self, model: str = "llama3", host: str | None = None) -> None:
        self.model, self.host = model, host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("Instale el extra opcional 'ollama' para usar OllamaAdapter.") from exc
        response = requests.post(
            f"{self.host.rstrip('/')}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False,
                  "options": {"num_predict": max_tokens}},
            timeout=30,
        )
        response.raise_for_status()
        return str(response.json().get("response", ""))
