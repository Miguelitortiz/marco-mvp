"""PDF parser with a clear optional dependency boundary."""
from pathlib import Path
from core.ports.parser_port import ParsedDocument


class PyMuPDFParser:
    def parse(self, path: str) -> ParsedDocument:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Instale el extra opcional 'pdf' para analizar PDF.") from exc
        source = Path(path)
        with fitz.open(source) as document:
            text = "\n".join(page.get_text() for page in document)
            pages = len(document)
        return ParsedDocument(text=text, metadata={"path": str(source), "pages": pages})

    def parse_pages(self, path: str) -> list[ParsedDocument]:
        """Return page-preserving documents for traceable RAG ingestion."""
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Instale el extra opcional 'pdf' para analizar PDF.") from exc
        source = Path(path)
        with fitz.open(source) as document:
            return [ParsedDocument(page.get_text(), {
                "path": str(source), "source": str(source), "page": number,
            }) for number, page in enumerate(document, 1)]


class PlainTextParser:
    def parse(self, path: str) -> ParsedDocument:
        source = Path(path)
        return ParsedDocument(source.read_text(encoding="utf-8"), {"path": str(source)})
