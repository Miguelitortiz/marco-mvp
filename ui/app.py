"""Real local Streamlit workbench; all optional imports stay behind UI actions."""
from pathlib import Path
import sys

# ``streamlit run ui/app.py`` places ``ui`` first on sys.path. Add the
# repository root so the source checkout works without an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.adapters import HybridRAGStore, JSONLAuditAdapter, MockLLMAdapter
from core.application import AuditService, DraftingService
from core.domain.fsm import InvalidStateTransitionError, WorkflowFSM
from core.domain.models import HumanSignature, WorkflowState
from core.services.governance import GovernanceService
from core.services.ingestion import ingest_file
from core.services.transparency import export_report, transparency_report


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="MARCO experimental", layout="wide")
    st.title("MARCO · workbench experimental auditable")
    if "fsm" not in st.session_state:
        st.session_state.fsm = WorkflowFSM(WorkflowState.PARAMETRIZATION)
        st.session_state.store = HybridRAGStore()
        st.session_state.text = ""
        st.session_state.hits = []
    fsm, store = st.session_state.fsm, st.session_state.store
    project_id = st.sidebar.text_input("Proyecto", "experimento")
    audit = AuditService(JSONLAuditAdapter(Path("data") / "audit.jsonl"), project_id)
    st.sidebar.subheader("Parametrización")
    target_words = st.sidebar.number_input("Palabras objetivo", 50, 10000, 500)
    tolerance = st.sidebar.slider("Tolerancia", 0.0, 1.0, 0.1)
    template = st.sidebar.text_input("Nombre de plantilla", "Sección experimental")
    current_words = len(st.session_state.text.split())
    lower_bound = int(target_words * (1 - tolerance))
    upper_bound = int(target_words * (1 + tolerance))
    st.sidebar.progress(min(1.0, current_words / max(1, upper_bound)), "Presupuesto de palabras")
    if current_words > upper_bound:
        st.sidebar.error(f"Exceso: {current_words} palabras; máximo {upper_bound}.")
    elif current_words < lower_bound:
        st.sidebar.warning(f"Por debajo de cuota: {current_words}; mínimo {lower_bound}.")
    else:
        st.sidebar.success(f"En rango: {current_words}/{target_words} palabras.")
    uploaded = st.sidebar.file_uploader("PDF o texto", type=["pdf", "txt"], accept_multiple_files=True)
    if st.sidebar.button("Indexar documentos") and uploaded:
        for item in uploaded:
            suffix = Path(item.name).suffix or ".txt"
            upload_dir = Path("data") / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            path = upload_dir / item.name
            path.write_bytes(item.getvalue())
            try:
                docs = ingest_file(path)
                store.add(docs)
                audit.record(WorkflowState.CURATION, "ui", "documents_indexed",
                             {"source": item.name, "chunks": len(docs)})
            except RuntimeError as exc:
                st.sidebar.error(str(exc))
        st.sidebar.success(f"{len(store.documents)} fragmentos indexados")

    st.caption(f"Fase actual: **{fsm.state.value}** · plantilla: {template} · tolerancia: {tolerance:.0%}")
    editor, inspector = st.columns([2, 1])
    with inspector:
        query = st.text_input("Buscar evidencia", "método resultados")
        if st.button("Buscar") or query:
            st.session_state.hits = store.search(query, top_k=5)
        for hit in st.session_state.hits:
            st.write(f"`{hit.document.document_id}` · {hit.document.metadata} · {hit.score:.4f}")
            st.caption(hit.document.text[:400])
    with editor:
        instruction = st.text_area("Instrucción de sección", "Redacta una sección basada en la evidencia.", height=90)
        if st.button("Redactar con MockLLM"):
            result = DraftingService(MockLLMAdapter(), store, budget_tokens=int(target_words)).draft(instruction, query=query)
            st.session_state.text = result.text
            audit.record(WorkflowState.DRAFTING, "ui", "draft_generated",
                         {"citations": [h.document.metadata for h in result.citations]},
                         input_tokens=result.input_tokens, output_tokens=result.output_tokens)
        st.session_state.text = st.text_area("Editor", st.session_state.text, height=260)
        current_words = len(st.session_state.text.split())
        if st.button("Ejecutar gobernanza"):
            gov = GovernanceService()
            l1, l2 = gov.level1(st.session_state.text), gov.level2(st.session_state.text, st.session_state.hits)
            st.write({"nivel_1": {"hallazgos": l1.findings, "score": l1.score, "flag": l1.flagged},
                      "nivel_2": {"score": l2.score, "semáforo": l2.flag}})
    st.subheader("Firma HITL y avance")
    user = st.text_input("Firmante", "investigador")
    decision = st.selectbox("Decisión", ["ACCEPTED", "AMENDED", "REJECTED"])
    if st.button("Firmar y avanzar"):
        next_state = {WorkflowState.PARAMETRIZATION: WorkflowState.CURATION,
                      WorkflowState.CURATION: WorkflowState.DRAFTING,
                      WorkflowState.DRAFTING: WorkflowState.ASSEMBLY}.get(fsm.state)
        if next_state is None:
            st.warning("La fase ya está ensamblada.")
        else:
            try:
                signature = HumanSignature(user_id=user, decision=decision, state_hash=f"{fsm.state.value}:{len(st.session_state.text)}")
                fsm.transition(next_state, {"human_signature": signature})
                audit.record(next_state, user, "transition_signed", {"decision": decision})
                st.success(f"Avanzó a {next_state.value}")
            except InvalidStateTransitionError as exc:
                st.error(str(exc))
    report_path = Path("data") / "audit.jsonl"
    if report_path.exists():
        report = transparency_report(report_path)
        st.subheader("Reporte de transparencia Secc. 4.6")
        st.json(report)
        if st.button("Exportar reporte JSON"):
            export_report(report, Path("data") / "transparency.json")
        if st.button("Exportar reporte Markdown"):
            export_report(report, Path("data") / "transparency.md", "markdown")


if __name__ == "__main__":
    main()
