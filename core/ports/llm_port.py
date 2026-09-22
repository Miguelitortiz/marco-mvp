"""Port for language-model providers."""
from typing import Protocol


class LLMPort(Protocol):
    def generate(self, prompt: str, *, max_tokens: int = 512) -> str: ...


__all__ = ["LLMPort"]
