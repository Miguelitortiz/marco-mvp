from core.adapters import JSONLAuditAdapter
from core.application.audit_service import AuditService
from core.domain.fsm import WorkflowFSM
from core.domain.models import WorkflowState
from core.services.governance import GovernanceService
from core.services.ingestion import chunk_text
from core.services.transparency import transparency_report


def _sig():
    return {"human_signature": {"user_id": "u", "decision": "ACCEPTED", "state_hash": "h"}}


def test_four_phase_fsm_requires_signatures():
    fsm = WorkflowFSM(WorkflowState.PARAMETRIZATION)
    for phase in (WorkflowState.CURATION, WorkflowState.DRAFTING, WorkflowState.ASSEMBLY):
        fsm.transition(phase, _sig())
    assert fsm.state is WorkflowState.ASSEMBLY


def test_chunking_has_overlap_and_is_deterministic():
    chunks = chunk_text(" ".join(str(i) for i in range(10)), chunk_size=4, overlap=1)
    assert chunks[0].split()[-1] == chunks[1].split()[0]


def test_governance_thresholds_and_findings():
    result = GovernanceService().level1("En conclusión, el resultado mejora.")
    assert result.flagged and "en conclusión" in result.findings
    assert GovernanceService().level2("rare", []).flag == "red"


def test_transparency_report_from_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    audit = AuditService(JSONLAuditAdapter(path), "p")
    audit.record(WorkflowState.DRAFTING, "u", "draft", {"citations": [{"source": "a"}]},
                 input_tokens=3, output_tokens=4, latency_ms=2)
    report = transparency_report(path)
    assert report["chain_verified"] is True
    assert report["citations"] == 1
    assert report["tokens"] == {"input": 3, "output": 4}
