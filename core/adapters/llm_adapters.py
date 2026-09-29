"""Safe, swappable LLM adapters.

The generic adapter uses the OpenAI-compatible HTTP contract, which is
supported by OpenAI, DeepSeek, Google Gemini, Groq, OpenRouter, LM Studio and
many other gateways. Ollama remains available through its native endpoint.
"""
import os
import json
from urllib import request, error
from typing import Any


class MockLLMAdapter:
    def __init__(self, response: str = "Borrador determinista basado en la evidencia.") -> None:
        self.response = response
        self.calls: list[tuple[str, int]] = []

    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        self.calls.append((prompt, max_tokens))
        return " ".join(self.response.split()[:max_tokens])


class OpenAICompatibleAdapter:
    """Call any provider exposing ``/v1/chat/completions``."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 90.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        if not self.api_key and not self.base_url.startswith(
            ("http://localhost", "http://127.0.0.1")
        ):
            raise RuntimeError("Este proveedor requiere una API key.")
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        endpoint = f"{self.base_url}/chat/completions"
        try:
            with request.urlopen(
                request.Request(endpoint, data=payload, headers=headers, method="POST"),
                timeout=self.timeout,
            ) as response:
                body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Error del proveedor LLM ({exc.code}): {detail[:500]}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"No se pudo conectar con el proveedor LLM: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Respuesta inválida del proveedor LLM.") from exc
        return str(content or "")


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


PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "OpenAI": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "DeepSeek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "Google Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
    },
    "OpenRouter": {"base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini"},
    "Groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "Local (LM Studio)": {
        "base_url": "http://localhost:1234/v1", "model": "local-model"
    },
    "Local (Ollama)": {"base_url": "http://localhost:11434", "model": "llama3.2"},
}


def create_llm_adapter(
    provider: str,
    *,
    model: str,
    api_key: str = "",
    base_url: str = "",
) -> MockLLMAdapter | OpenAICompatibleAdapter | OllamaAdapter:
    if provider == "Mock (offline)":
        return MockLLMAdapter()
    if provider == "Local (Ollama)":
        return OllamaAdapter(model=model, host=base_url or "http://localhost:11434")
    preset = PROVIDER_PRESETS.get(provider)
    if preset is None:
        raise ValueError(f"Proveedor no soportado: {provider}")
    return OpenAICompatibleAdapter(
        model=model, api_key=api_key, base_url=base_url or preset["base_url"]
    )
