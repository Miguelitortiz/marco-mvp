"""Opt-in Grobid parser adapter.

The adapter only contacts a caller-provided Grobid endpoint when ``parse`` is
called; the default application never instantiates it.
"""

from pathlib import Path
from urllib import request

from core.ports.parser_port import ParsedDocument


class GrobidParser:
    def __init__(self, endpoint: str = "http://localhost:8070/api/processFulltextDocument",
                 timeout: float = 30.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def parse(self, path: str) -> ParsedDocument:
        source = Path(path)
        boundary = b"----MARCO-GROBID"
        content = source.read_bytes()
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="input"; filename="' +
            source.name.encode() + b'"\r\nContent-Type: application/pdf\r\n\r\n' +
            content + b"\r\n--" + boundary + b"--\r\n"
        )
        req = request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            text = response.read().decode("utf-8")
        return ParsedDocument(text=text, metadata={"source": str(source), "parser": "grobid"})
