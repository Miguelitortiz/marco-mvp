"""PDF/text ingestion and deterministic chunking for the local RAG store."""
from hashlib import sha256
from pathlib import Path
import re
from core.ports.vector_store import VectorDocument
from core.ports.parser_port import ParsedDocument, ParserPort


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than chunk_size")
    words = re.findall(r"\S+", text)
    step = chunk_size - overlap
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), step) if words[i:i + chunk_size]]


def ingest_pdf(path: str | Path, *, chunk_size: int = 800, overlap: int = 120) -> list[VectorDocument]:
    source = Path(path)
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Instale el extra opcional 'pdf' (PyMuPDF) para indexar PDF.") from exc
    documents: list[VectorDocument] = []
    with fitz.open(source) as pdf:
        for page_number, page in enumerate(pdf, 1):
            for chunk_number, text in enumerate(chunk_text(page.get_text(), chunk_size, overlap)):
                stable = sha256(f"{source.resolve()}|{page_number}|{chunk_number}|{text}".encode()).hexdigest()[:16]
                documents.append(VectorDocument(
                    f"{source.stem}:{page_number}:{chunk_number}:{stable}",
                    text,
                    {"source": str(source), "page": page_number, "chunk": chunk_number},
                ))
    return documents


def ingest_file(path: str | Path, **kwargs: int) -> list[VectorDocument]:
    return ingest_pdf(path, **kwargs) if Path(path).suffix.lower() == ".pdf" else [
        VectorDocument(f"{Path(path).name}:0:0", Path(path).read_text(encoding="utf-8"),
                       {"source": str(path), "page": 1, "chunk": 0})
    ]


def documents_from_parsed(
    parsed: ParsedDocument,
    *,
    source: str,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[VectorDocument]:
    """Convert any parser output into traceable retrieval documents."""
    documents: list[VectorDocument] = []
    for chunk_number, text in enumerate(chunk_text(parsed.text, chunk_size, overlap)):
        stable = sha256(f"{source}|{chunk_number}|{text}".encode()).hexdigest()[:16]
        metadata = dict(parsed.metadata)
        metadata.update({"source": source, "page": metadata.get("page", 1), "chunk": chunk_number})
        documents.append(VectorDocument(
            f"{Path(source).stem}:1:{chunk_number}:{stable}", text, metadata
        ))
    return documents


def ingest_with_parser(
    path: str | Path,
    parser: ParserPort,
    *,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[VectorDocument]:
    source = Path(path)
    return documents_from_parsed(
        parser.parse(str(source)), source=str(source),
        chunk_size=chunk_size, overlap=overlap,
    )
