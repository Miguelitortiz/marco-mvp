"""Deterministic lexical and semantic diffing for human review."""
from dataclasses import dataclass
import difflib
import math
import re
from collections.abc import Callable, Sequence


@dataclass(frozen=True)
class DiffResult:
    unified: str
    additions: int
    deletions: int
    changed: bool
    lexical_similarity: float
    semantic_similarity: float | None
    drift: str


class DiffService:
    def __init__(
        self,
        embedder: Callable[[str], Sequence[float]] | None = None,
    ) -> None:
        self.embedder = embedder

    def compare(self, before: str, after: str, *, fromfile: str = "before",
                tofile: str = "after",
                embedding_before: Sequence[float] | None = None,
                embedding_after: Sequence[float] | None = None) -> DiffResult:
        lines = list(difflib.unified_diff(
            before.splitlines(), after.splitlines(), fromfile=fromfile,
            tofile=tofile, lineterm="",
        ))
        lexical = difflib.SequenceMatcher(None, before, after).ratio()
        if embedding_before is None and self.embedder is not None:
            embedding_before = self.embedder(before)
        if embedding_after is None and self.embedder is not None:
            embedding_after = self.embedder(after)
        semantic = self.cosine_similarity(embedding_before, embedding_after)
        return DiffResult(
            unified="\n".join(lines),
            additions=sum(1 for line in lines if line.startswith("+") and not line.startswith("+++")),
            deletions=sum(1 for line in lines if line.startswith("-") and not line.startswith("---")),
            changed=before != after,
            lexical_similarity=lexical,
            semantic_similarity=semantic,
            drift=self.classify_drift(semantic if semantic is not None else lexical),
        )

    diff = compare

    @staticmethod
    def cosine_similarity(
        left: Sequence[float] | None, right: Sequence[float] | None
    ) -> float | None:
        if left is None or right is None or len(left) != len(right) or not left:
            return None
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)

    @staticmethod
    def classify_drift(similarity: float) -> str:
        if similarity >= 0.85:
            return "green"
        if similarity >= 0.65:
            return "yellow"
        return "red"

    @staticmethod
    def normalized_levenshtein(left: str, right: str) -> float:
        """Return edit distance normalized to the longer input length."""
        previous = list(range(len(right) + 1))
        for i, left_char in enumerate(left, 1):
            current = [i]
            for j, right_char in enumerate(right, 1):
                current.append(min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_char != right_char),
                ))
            previous = current
        denominator = max(len(left), len(right), 1)
        return previous[-1] / denominator
