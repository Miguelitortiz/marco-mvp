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


@dataclass(frozen=True)
class Level3Result:
    signed: bool
    signer: str | None
    decision: str | None
    flag: str


class GovernanceService:
    def __init__(self, fillers: tuple[str, ...] = DEFAULT_FILLERS, *,
                 semantic_green: float = 0.75, semantic_red: float = 0.50,
                 green_threshold: float | None = None,
                 red_threshold: float | None = None) -> None:
        self.fillers = tuple(item.lower() for item in fillers)
        self.semantic_green = green_threshold if green_threshold is not None else semantic_green
        self.semantic_red = red_threshold if red_threshold is not None else semantic_red
        if not 0 <= self.semantic_red <= self.semantic_green <= 1:
            raise ValueError("semantic thresholds must satisfy 0 <= red <= green <= 1")

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
        flag = ("green" if score >= self.semantic_green else
                "yellow" if score >= self.semantic_red else "red")
        return Level2Result(rows, round(score, 4), flag)

    @staticmethod
    def level3(signature: object | None = None) -> Level3Result:
        if signature is None:
            return Level3Result(False, None, None, "red")
        if isinstance(signature, dict):
            signature = signature.get("human_signature", signature)
            signer = signature.get("user_id") if isinstance(signature, dict) else None
            decision = signature.get("decision") if isinstance(signature, dict) else None
        else:
            signer = getattr(signature, "user_id", None)
            decision = getattr(signature, "decision", None)
        signed = bool(signer and decision in {"ACCEPTED", "AMENDED", "REJECTED"})
        return Level3Result(signed, signer, decision, "green" if signed else "red")

    def run(self, text: str, citations: list[object] | None = None,
            signature: object | None = None) -> dict[str, object]:
        return {"level1": self.level1(text), "level2": self.level2(text, citations),
                "level3": self.level3(signature)}
