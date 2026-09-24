"""Application service for tamper-evident event recording."""
from datetime import datetime, timezone
import hashlib
import json
import uuid
from core.domain.models import AuditEvent, WorkflowState
from core.ports.audit_port import AuditPort


class AuditService:
    def __init__(self, audit_port: AuditPort, project_id: str) -> None:
        self.audit_port, self.project_id = audit_port, project_id

    def record(
        self, phase: WorkflowState, actor: str, action_type: str,
        payload: dict[str, object] | None = None, **usage: object,
    ) -> AuditEvent:
        prior = self.audit_port.list_events(self.project_id)
        previous = prior[-1].event_hash if prior else None
        timestamp = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())
        body = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "project_id": self.project_id,
            "phase": phase.value,
            "actor": actor,
            "action_type": action_type,
            "payload": payload or {},
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "latency_ms": float(usage.get("latency_ms", 0.0) or 0.0),
            "previous_event_hash": previous,
        }
        digest = self._hash(body)
        event = AuditEvent(
            event_id=event_id, timestamp=timestamp,
            project_id=self.project_id, phase=phase, actor=actor,
            action_type=action_type, payload=payload or {},
            previous_event_hash=previous, event_hash=digest,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            latency_ms=float(usage.get("latency_ms", 0.0) or 0.0),
        )
        return self.audit_port.append(event)

    append_event = record

    def inspect_evidence(self, phase: WorkflowState, actor: str, fragment_id: str,
                         notes: str = "") -> AuditEvent:
        return self.record(phase, actor, "evidence_inspected",
                           {"fragment_id": fragment_id, "notes": notes})

    def record_human_edit(self, phase: WorkflowState, actor: str, before: str,
                          after: str) -> AuditEvent:
        return self.record(phase, actor, "human_edit",
                           {
                               "before_length": len(before),
                               "after_length": len(after),
                               "text": after,
                               "delta_characters": len(after) - len(before),
                           })

    def rollback(self, phase: WorkflowState, actor: str, target_event_hash: str,
                 reason: str = "") -> AuditEvent:
        """Record a non-linear rollback; history remains append-only."""
        if not target_event_hash:
            raise ValueError("target_event_hash is required")
        return self.record(phase, actor, "rollback",
                           {"target_event_hash": target_event_hash, "reason": reason})

    def verify_chain(self) -> bool:
        events = self.audit_port.list_events(self.project_id)
        previous = None
        for event in events:
            if event.previous_event_hash != previous:
                return False
            body = event.model_dump(mode="json", exclude={"event_hash"})
            expected = self._hash(body)
            if expected != event.event_hash:
                return False
            previous = event.event_hash
        return True

    @staticmethod
    def _hash(body: dict[str, object]) -> str:
        canonical = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
