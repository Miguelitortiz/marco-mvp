"""Append-only JSONL audit storage."""
import json
from pathlib import Path
from core.domain.models import AuditEvent


class JSONLAuditAdapter:
    def __init__(self, path: str | Path = "trajectory.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent) -> AuditEvent:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
        return event

    def list_events(self, project_id: str | None = None) -> list[AuditEvent]:
        if not self.path.exists():
            return []
        events = [
            AuditEvent.model_validate(json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        return [event for event in events if project_id is None or event.project_id == project_id]
