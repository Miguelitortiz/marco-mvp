from core.adapters import HybridRAGStore, JSONLAuditAdapter, MockLLMAdapter
from core.application import AuditService, DiffService, DraftingService
from core.domain.models import WorkflowState
from core.ports.vector_store import VectorDocument


def test_audit_chain_and_diff(tmp_path):
    service = AuditService(JSONLAuditAdapter(tmp_path / "audit.jsonl"), "p1")
    service.record(WorkflowState.DRAFTING, "test", "draft")
    service.record(WorkflowState.HUMAN_REVIEW, "test", "review")
    assert service.verify_chain()
    result = DiffService().compare("a\n", "a\nb\n")
    assert result.changed and result.additions == 1


def test_deterministic_rag_and_budget():
    store = HybridRAGStore()
    store.add([VectorDocument("a", "solar energy improves storage"),
               VectorDocument("b", "unrelated text")])
    assert store.search("solar storage")[0].document.document_id == "a"
    draft = DraftingService(MockLLMAdapter("one two three four"), store, budget_tokens=20).draft(
        "Summarize", query="solar"
    )
    assert draft.citations and draft.text
