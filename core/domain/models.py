"""Framework-independent domain models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    # The four canonical MARCO phases.  Legacy states remain below so old
    # audit logs and integrations can still be read.
    PARAMETRIZATION = "PARAMETRIZATION"
    CURATION = "CURATION"
    DRAFTING = "DRAFTING"
    ASSEMBLY = "ASSEMBLY"
    IDLE = "IDLE"
    CORPUS_INGESTION = "CORPUS_INGESTION"
    QUERY_EXPANSION = "QUERY_EXPANSION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    TRANSITION_GATE = "TRANSITION_GATE"
    EXPORT = "EXPORT"


class HumanSignature(BaseModel):
    user_id: str = Field(min_length=1)
    decision: str
    state_hash: str = Field(min_length=1)


class AuditEvent(BaseModel):
    event_id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    project_id: str = Field(min_length=1)
    phase: WorkflowState
    actor: str
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    latency_ms: float | None = 0.0
    previous_event_hash: str | None = None
    event_hash: str = Field(min_length=1)
