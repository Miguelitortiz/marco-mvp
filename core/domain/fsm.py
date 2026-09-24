"""Deterministic workflow state machine with a human transition gate."""

from collections.abc import Mapping
from typing import Any

from .models import HumanSignature, WorkflowState


class InvalidStateTransitionError(ValueError):
    """Raised when a workflow transition violates the domain rules."""


class WorkflowFSM:
    """Controls legal phase changes and requires a human signature."""

    _transitions: dict[WorkflowState, WorkflowState] = {
        WorkflowState.PARAMETRIZATION: WorkflowState.CURATION,
        WorkflowState.CURATION: WorkflowState.DRAFTING,
        WorkflowState.IDLE: WorkflowState.CORPUS_INGESTION,
        WorkflowState.CORPUS_INGESTION: WorkflowState.QUERY_EXPANSION,
        WorkflowState.QUERY_EXPANSION: WorkflowState.DRAFTING,
        WorkflowState.DRAFTING: WorkflowState.HUMAN_REVIEW,
        WorkflowState.HUMAN_REVIEW: WorkflowState.TRANSITION_GATE,
        WorkflowState.TRANSITION_GATE: WorkflowState.EXPORT,
    }

    def __init__(self, state: WorkflowState = WorkflowState.IDLE) -> None:
        self.state = state
        self._canonical = state in {
            WorkflowState.PARAMETRIZATION, WorkflowState.CURATION,
            WorkflowState.DRAFTING, WorkflowState.ASSEMBLY,
        }

    def transition(
        self,
        target: WorkflowState,
        payload: Mapping[str, Any] | None = None,
    ) -> WorkflowState:
        payload = payload or {}
        expected = (
            {WorkflowState.PARAMETRIZATION: WorkflowState.CURATION,
             WorkflowState.CURATION: WorkflowState.DRAFTING,
             WorkflowState.DRAFTING: WorkflowState.ASSEMBLY}.get(self.state)
            if self._canonical else self._transitions.get(self.state)
        )
        if expected != target:
            raise InvalidStateTransitionError(
                f"Cannot transition from {self.state.value} to {target.value}; "
                f"expected {expected.value if expected else 'no target'}."
            )

        canonical = {WorkflowState.PARAMETRIZATION, WorkflowState.CURATION,
                     WorkflowState.DRAFTING, WorkflowState.ASSEMBLY}
        if (target in {WorkflowState.CURATION, WorkflowState.DRAFTING, WorkflowState.ASSEMBLY}
                and self.state in canonical) or target in {
                    WorkflowState.TRANSITION_GATE, WorkflowState.EXPORT
                }:
            self._require_signature(payload)

        self.state = target
        self._canonical = self._canonical or target in {
            WorkflowState.PARAMETRIZATION, WorkflowState.CURATION, WorkflowState.ASSEMBLY
        }
        return self.state

    def rollback(
        self,
        target: WorkflowState,
        payload: Mapping[str, Any] | None = None,
    ) -> WorkflowState:
        """Move to an earlier canonical phase after an explicit human decision."""
        canonical_order = {
            WorkflowState.PARAMETRIZATION: 0,
            WorkflowState.CURATION: 1,
            WorkflowState.DRAFTING: 2,
            WorkflowState.ASSEMBLY: 3,
        }
        if not self._canonical or target not in canonical_order:
            raise InvalidStateTransitionError(
                "Rollback is only available inside the four canonical MARCO phases."
            )
        if canonical_order[target] >= canonical_order.get(self.state, -1):
            raise InvalidStateTransitionError(
                f"Rollback target {target.value} is not earlier than {self.state.value}."
            )
        self._require_signature(payload or {})
        self.state = target
        self._canonical = True
        return self.state

    @staticmethod
    def _require_signature(payload: Mapping[str, Any]) -> HumanSignature:
        raw_signature = payload.get("human_signature")
        if raw_signature is None:
            raise InvalidStateTransitionError(
                "A human_signature is required for this transition."
            )
        try:
            signature = (
                raw_signature
                if isinstance(raw_signature, HumanSignature)
                else HumanSignature.model_validate(raw_signature)
            )
        except Exception as exc:
            raise InvalidStateTransitionError(
                "human_signature must include user_id, decision, and state_hash."
            ) from exc
        if signature.decision not in {"ACCEPTED", "REJECTED", "AMENDED"}:
            raise InvalidStateTransitionError("human_signature has an invalid decision.")
        return signature
