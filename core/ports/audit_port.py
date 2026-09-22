"""Append-only audit port."""
from typing import Protocol
from core.domain.models import AuditEvent


class AuditPort(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...
    def list_events(self, project_id: str | None = None) -> list[AuditEvent]: ...


__all__ = ["AuditPort"]
