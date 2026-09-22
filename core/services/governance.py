"""Offline, deterministic governance checks for generated scientific prose."""
from dataclasses import dataclass
import hashlib
import math
import re


DEFAULT_FILLERS = (
    "en conclusión", "cabe destacar", "es importante señalar",
    "en el contexto actual", "sin lugar a dudas", "como modelo de lenguaje",
    "se puede decir que",
)


@dataclass(frozen=True)
class Level1Result:
    text: str
    findings: list[str]
    score: float
    flagged: bool


@dataclass(frozen=True)
class Level2Result:
    citations: list[dict[str, object]]
    score: float
    flag: str


class GovernanceService:
    def __init__(self, fillers: tuple[str, ...] = DEFAULT_FILLERS) -> None:
        self.fillers = tuple(item.lower() for item in fillers)

    def level1(self, text: str) -> Level1Result:
        findings = [phrase for phrase in self.fillers if phrase in text.lower()]
        words = max(1, len(re.findall(r"\w+", text, flags=re.UNICODE)))
        score = max(0.0, 1.0 - len(findings) / words * 5.0)
        return Level1Result(text, findings, round(score, 4), bool(findings))

    @staticmethod
    def _vector(text: str, dimensions: int = 64) -> list[float]:
        values = [0.0] * dimensions
        for token in re.findall(r"\w+", text.lower(), flags=re.UNICODE):
            digest = hashlib.sha256(token.encode()).digest()
            i = int.from_bytes(digest[:4], "big") % dimensions
            values[i] += 1 if digest[4] & 1 else -1
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def level2(self, text: str, citations: list[object] | None = None) -> Level2Result:
        items = citations or []
        rows = []
        for citation in items:
            evidence = getattr(getattr(citation, "document", citation), "text", str(citation))
            score = sum(a * b for a, b in zip(self._vector(text), self._vector(evidence)))
            score = max(0.0, min(1.0, (score + 1.0) / 2.0))
            rows.append({"evidence": evidence, "score": round(score, 4)})
        score = sum(float(row["score"]) for row in rows) / len(rows) if rows else 0.0
        flag = "green" if score >= 0.82 else "yellow" if score >= 0.55 else "red"
        return Level2Result(rows, round(score, 4), flag)

    def run(self, text: str, citations: list[object] | None = None) -> dict[str, object]:
        return {"level1": self.level1(text), "level2": self.level2(text, citations)}
