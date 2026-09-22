import pytest

from core.domain.fsm import InvalidStateTransitionError, WorkflowFSM
from core.domain.models import WorkflowState


def signature() -> dict[str, dict[str, str]]:
    return {
        "human_signature": {
            "user_id": "researcher-1",
            "decision": "ACCEPTED",
            "state_hash": "abc123",
        }
    }


def test_initial_state_and_legal_progression() -> None:
    fsm = WorkflowFSM()
    for target in (
        WorkflowState.CORPUS_INGESTION,
        WorkflowState.QUERY_EXPANSION,
        WorkflowState.DRAFTING,
        WorkflowState.HUMAN_REVIEW,
    ):
        assert fsm.transition(target) is target

    assert fsm.transition(WorkflowState.TRANSITION_GATE, signature()) is WorkflowState.TRANSITION_GATE
    assert fsm.transition(WorkflowState.EXPORT, signature()) is WorkflowState.EXPORT


def test_cannot_skip_human_review_or_use_wrong_target() -> None:
    fsm = WorkflowFSM()
    with pytest.raises(InvalidStateTransitionError):
        fsm.transition(WorkflowState.DRAFTING)


def test_transition_gate_requires_valid_human_signature() -> None:
    fsm = WorkflowFSM(WorkflowState.HUMAN_REVIEW)

    with pytest.raises(InvalidStateTransitionError):
        fsm.transition(WorkflowState.TRANSITION_GATE)
    with pytest.raises(InvalidStateTransitionError):
        fsm.transition(
            WorkflowState.TRANSITION_GATE,
            {"human_signature": {"user_id": "u", "decision": "AUTO", "state_hash": "h"}},
        )

