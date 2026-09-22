"""Ports and value objects for retrieval."""
from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass(frozen=True)
class VectorDocument:
    document_id: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    document: VectorDocument
    score: float
    source: str = "hybrid"


class VectorStorePort(Protocol):
    def add(self, documents: Sequence[VectorDocument]) -> None: ...
    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]: ...


__all__ = ["VectorDocument", "SearchHit", "VectorStorePort"]
