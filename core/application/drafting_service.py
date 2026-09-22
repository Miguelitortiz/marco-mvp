"""Budget-aware, provider-independent drafting service."""
from dataclasses import dataclass
from core.ports.llm_port import LLMPort
from core.ports.vector_store import SearchHit, VectorStorePort


@dataclass(frozen=True)
class DraftResult:
    text: str
    citations: list[SearchHit]
    input_tokens: int
    output_tokens: int
    truncated: bool = False


class DraftingService:
    def __init__(self, llm: LLMPort, retriever: VectorStorePort | None = None,
                 *, budget_tokens: int = 2048) -> None:
        self.llm, self.retriever, self.budget_tokens = llm, retriever, budget_tokens

    def draft(self, instruction: str, *, query: str | None = None,
              top_k: int = 5) -> DraftResult:
        hits = self.retriever.search(query or instruction, top_k=top_k) if self.retriever else []
        context = "\n\n".join(
            f"[{hit.document.document_id}] {hit.document.text}" for hit in hits
        )
        prompt = f"{instruction}\n\nEvidence:\n{context}" if context else instruction
        input_tokens = len(prompt.split())
        available = max(1, self.budget_tokens - min(input_tokens, self.budget_tokens))
        text = self.llm.generate(prompt, max_tokens=available)
        words = text.split()
        truncated = len(words) > available
        if truncated:
            text = " ".join(words[:available])
        return DraftResult(text, hits, input_tokens, len(text.split()), truncated)
