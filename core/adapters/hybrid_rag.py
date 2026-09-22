"""Local hybrid retrieval with sparse, dense and RRF ranking."""
from collections import Counter
import hashlib
import math
import re
from core.ports.vector_store import SearchHit, VectorDocument


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


class HybridRAGStore:
    def __init__(self, *, embedding_dimensions: int = 128) -> None:
        self.documents: list[VectorDocument] = []
        self.embedding_dimensions = embedding_dimensions

    def add(self, documents: list[VectorDocument] | tuple[VectorDocument, ...]) -> None:
        self.documents.extend(documents)

    def _embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.embedding_dimensions
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.embedding_dimensions
            vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        if not self.documents or top_k <= 0:
            return []
        query_tokens = _tokens(query)
        q_counts = Counter(query_tokens)
        q_vec = self._embedding(query)
        document_frequency = Counter(
            token for document in self.documents for token in set(_tokens(document.text))
        )
        sparse_scores: list[tuple[float, VectorDocument]] = []
        dense_scores: list[tuple[float, VectorDocument]] = []
        for document in self.documents:
            tokens = _tokens(document.text)
            tf = Counter(tokens)
            bm25 = sum(
                (tf[token] * 2.2 / (tf[token] + 1.2))
                * math.log((len(self.documents) + 1) / (document_frequency[token] + 1))
                for token in q_counts if token in tf
            )
            vector = self._embedding(document.text)
            cosine = sum(a * b for a, b in zip(q_vec, vector))
            sparse_scores.append((bm25, document))
            dense_scores.append((cosine, document))
        sparse_scores.sort(key=lambda item: (-item[0], item[1].document_id))
        dense_scores.sort(key=lambda item: (-item[0], item[1].document_id))
        ranks: dict[str, float] = {}
        by_id = {document.document_id: document for document in self.documents}
        for rank, (_, document) in enumerate(sparse_scores, 1):
            ranks[document.document_id] = ranks.get(document.document_id, 0.0) + 1 / (60 + rank)
        for rank, (_, document) in enumerate(dense_scores, 1):
            ranks[document.document_id] = ranks.get(document.document_id, 0.0) + 1 / (60 + rank)
        ranked = sorted(ranks.items(), key=lambda item: (-item[1], item[0]))
        return [SearchHit(by_id[document_id], score, "rrf") for document_id, score in ranked[:top_k]]


HybridRAGAdapter = HybridRAGStore
