"""Document parsing port."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


class ParserPort(Protocol):
    def parse(self, path: str) -> ParsedDocument: ...


__all__ = ["ParsedDocument", "ParserPort"]
