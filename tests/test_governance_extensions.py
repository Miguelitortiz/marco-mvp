import pytest

from core.application.audit_service import AuditService
from core.adapters.audit_adapter import JSONLAuditAdapter
from core.domain.configuration import load_governance_config
from core.domain.models import WorkflowState
from core.domain.fsm import InvalidStateTransitionError, WorkflowFSM
from core.services.budget import BudgetEnforcer
from core.services.governance import GovernanceService
from core.services.transparency import transparency_report


def test_optional_yaml_and_budget(tmp_path):
    path = tmp_path / "governance.yaml"
    path.write_text("template: Methods\nbudget:\n  target_words: 10\n  tolerance: 0.2\n", encoding="utf-8")
    config = load_governance_config(path)
    assert config.template == "Methods"
    assert BudgetEnforcer(**config.budget.model_dump()).check("one two three").within_budget is False


def test_level3_defaults_and_configurable_semantics():
    service = GovernanceService(semantic_green=0.75, semantic_red=0.50)
    assert service.level3({"user_id": "ana", "decision": "ACCEPTED", "state_hash": "x"}).signed
    assert service.level3().flag == "red"
    assert service.level2("rare", []).flag == "red"


def test_audit_events_rollback_and_report_metrics(tmp_path):
    audit = AuditService(JSONLAuditAdapter(tmp_path / "trajectory.jsonl"), "p")
    event = audit.record(WorkflowState.DRAFTING, "LLM", "draft",
                         {"text": "one two", "alert_attended": True})
    audit.record_human_edit(WorkflowState.DRAFTING, "HUMAN", "one", "one two three")
    audit.rollback(WorkflowState.DRAFTING, "HUMAN", event.event_hash, "correction")
    report = transparency_report(tmp_path / "trajectory.jsonl")
    assert report["rollbacks"] == 1
    assert report["human_edits"] == 1
    assert report["llm_text_words"] == 2
    assert report["human_text_words"] == 3
    assert report["human_word_share"] == 0.6
    assert report["chain_verified"] is True


def test_fsm_rollback_requires_signature_and_moves_to_earlier_phase():
    fsm = WorkflowFSM(WorkflowState.DRAFTING)
    with pytest.raises(InvalidStateTransitionError):
        fsm.rollback(WorkflowState.CURATION)
    assert fsm.rollback(
        WorkflowState.CURATION,
        {"human_signature": {"user_id": "ana", "decision": "AMENDED", "state_hash": "h"}},
    ) is WorkflowState.CURATION
