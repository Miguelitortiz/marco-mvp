"""Streamlit interface for the MARCO scientific co-authoring workbench."""
from pathlib import Path
import sys

# ``streamlit run ui/app.py`` places ``ui`` first on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.adapters import (  # noqa: E402
    HybridRAGStore,
    JSONLAuditAdapter,
    PROVIDER_PRESETS,
    create_llm_adapter,
)
from core.application import AuditService, DraftingService  # noqa: E402
from core.domain.configuration import load_governance_config  # noqa: E402
from core.domain.fsm import InvalidStateTransitionError, WorkflowFSM  # noqa: E402
from core.domain.models import HumanSignature, WorkflowState  # noqa: E402
from core.services.governance import GovernanceService  # noqa: E402
from core.services.ingestion import ingest_file  # noqa: E402
from core.services.transparency import export_report, transparency_report  # noqa: E402


PHASES = (
    (WorkflowState.PARAMETRIZATION, "Preparar", "Definir alcance y presupuesto"),
    (WorkflowState.CURATION, "Curar", "Indexar y revisar evidencia"),
    (WorkflowState.DRAFTING, "Redactar", "Construir y revisar el texto"),
    (WorkflowState.ASSEMBLY, "Ensamblar", "Cerrar el expediente auditable"),
)


def _inject_styles(st) -> None:
    st.markdown(
        """
        <style>
        :root { --marco-ink: #18212b; --marco-muted: #5f6b76; --marco-blue: #145da0;
                --marco-line: #d9e1e8; --marco-paper: #f6f8fa; --marco-green: #2f6f4e; }
        .stApp { background: #f6f8fa; color: var(--marco-ink); }
        [data-testid="stHeader"] { background: rgba(246,248,250,.92); }
        [data-testid="stSidebar"] { background: #edf2f6; border-right: 1px solid var(--marco-line); }
        [data-testid="stSidebar"] > div:first-child { padding-top: 2rem; }
        .marco-kicker { color: var(--marco-blue); font-size: .72rem; font-weight: 700;
                        letter-spacing: .16em; text-transform: uppercase; margin-bottom: .35rem; }
        .marco-title { color: var(--marco-ink); font-family: Georgia, serif; font-size: 2.3rem;
                       line-height: 1.08; margin: 0; }
        .marco-lead { color: var(--marco-muted); font-size: 1rem; margin: .65rem 0 1.5rem; }
        .marco-rule { border-top: 1px solid var(--marco-line); margin: 1.1rem 0 1.4rem; }
        .marco-card { background: white; border: 1px solid var(--marco-line); border-radius: 4px;
                      padding: 1rem 1.15rem; min-height: 5.2rem; }
        .marco-card-label { color: var(--marco-muted); font-size: .72rem; text-transform: uppercase;
                            letter-spacing: .09em; font-weight: 700; }
        .marco-card-value { color: var(--marco-ink); font-size: 1.35rem; font-weight: 700;
                            margin-top: .3rem; }
        .marco-phase { border-left: 4px solid var(--marco-blue); background: white;
                       padding: .75rem 1rem; margin: .5rem 0 1rem; }
        .marco-phase strong { color: var(--marco-ink); }
        div[data-testid="stMetric"] { background: white; border: 1px solid var(--marco-line);
                                      padding: .75rem; }
        div[data-testid="stButton"] > button, div[data-testid="stFormSubmitButton"] > button {
            border-radius: 3px; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _phase_name(state: WorkflowState) -> str:
    return next(label for phase, label, _ in PHASES if phase == state)


def _next_phase(state: WorkflowState) -> WorkflowState | None:
    return {
        WorkflowState.PARAMETRIZATION: WorkflowState.CURATION,
        WorkflowState.CURATION: WorkflowState.DRAFTING,
        WorkflowState.DRAFTING: WorkflowState.ASSEMBLY,
    }.get(state)


def _initialise(st) -> None:
    if "fsm" not in st.session_state:
        st.session_state.fsm = WorkflowFSM(WorkflowState.PARAMETRIZATION)
        st.session_state.store = HybridRAGStore()
        st.session_state.text = ""
        st.session_state.hits = []
        st.session_state.last_governance = None
        st.session_state.inspected_fragments = set()


def _render_phase_rail(st, current: WorkflowState) -> None:
    st.markdown('<div class="marco-kicker">Expediente MARCO</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="marco-title">Coautoría científica<br>con trazabilidad</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="marco-lead">Un espacio de trabajo institucional para construir '
        "secciones con evidencia, revisión humana y registro auditable.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("**Ruta de trabajo**")
    for phase, label, description in PHASES:
        if phase == current:
            marker, style = "●", "color:#145da0"
        elif list(WorkflowState).index(phase) < list(WorkflowState).index(current):
            marker, style = "✓", "color:#2f6f4e"
        else:
            marker, style = "○", "color:#8a96a1"
        st.markdown(
            f'<div style="margin:.8rem 0;color:#5f6b76"><span style="{style};'
            f'font-size:1.1rem">{marker}</span>&nbsp; <strong style="color:#18212b">'
            f"{label}</strong><br><small style='margin-left:1.55rem'>{description}</small></div>",
            unsafe_allow_html=True,
        )


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="MARCO · Expediente científico", page_icon="▦", layout="wide")
    _inject_styles(st)
    _initialise(st)
    fsm, store = st.session_state.fsm, st.session_state.store
    config = load_governance_config(Path("governance.yaml"))
    project_id = st.sidebar.text_input("Identificador del expediente", "experimento")
    audit = AuditService(JSONLAuditAdapter(Path("data") / "trajectory.jsonl"), project_id)

    _render_phase_rail(st, fsm.state)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Configuración del expediente**")
    target_words = st.sidebar.number_input(
        "Palabras objetivo", 50, 10000, config.budget.target_words,
        help="Límite de referencia para la redacción y la revisión.",
    )
    tolerance = st.sidebar.slider("Tolerancia del presupuesto", 0.0, 0.9, config.budget.tolerance)
    template = st.sidebar.text_input("Plantilla o sección", "Sección experimental")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Motor de redacción**")
    providers = ["Mock (offline)", *PROVIDER_PRESETS]
    provider = st.sidebar.selectbox(
        "Proveedor", providers,
        help="La opción Mock funciona sin red. Las claves remotas solo viven en esta sesión.",
    )
    preset = PROVIDER_PRESETS.get(provider, {})
    model = st.sidebar.text_input("Modelo", preset.get("model", ""))
    base_url = st.sidebar.text_input("Endpoint", preset.get("base_url", ""))
    api_key = ""
    if provider not in {"Mock (offline)", "Local (Ollama)", "Local (LM Studio)"}:
        api_key = st.sidebar.text_input("API key", type="password")
    if provider == "Local (Ollama)":
        st.sidebar.caption("Ollama debe estar activo y tener el modelo descargado.")
    elif provider == "Local (LM Studio)":
        st.sidebar.caption("Activa el servidor local de LM Studio en el endpoint indicado.")

    current_words = len(st.session_state.text.split())
    lower_bound, upper_bound = int(target_words * (1 - tolerance)), int(target_words * (1 + tolerance))
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Control de extensión**")
    st.sidebar.progress(min(1.0, current_words / max(1, upper_bound)))
    if current_words > upper_bound:
        st.sidebar.error(f"Fuera de rango: {current_words} palabras (máximo {upper_bound}).")
    elif current_words < lower_bound:
        st.sidebar.warning(f"Pendiente: {current_words} palabras (mínimo {lower_bound}).")
    else:
        st.sidebar.success(f"En rango: {current_words} de {target_words} palabras.")

    st.markdown(
        f'<div class="marco-kicker">Fase {list(WorkflowState).index(fsm.state) + 1} de 4</div>'
        f'<div class="marco-phase"><strong>{_phase_name(fsm.state)}</strong> · '
        f'{fsm.state.value}<br><small>{template} · presupuesto con tolerancia del '
        f'{tolerance:.0%}</small></div>',
        unsafe_allow_html=True,
    )
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Fragmentos indexados", len(store.documents))
    metric_b.metric("Evidencias seleccionadas", len(st.session_state.hits))
    metric_c.metric("Palabras redactadas", current_words)

    st.markdown('<div class="marco-rule"></div>', unsafe_allow_html=True)
    editor, evidence, record = st.tabs(["01 · Redacción", "02 · Evidencia", "03 · Registro"])

    with editor:
        st.subheader("Redacción de la sección")
        st.caption("Trabaja de arriba hacia abajo: define la instrucción, genera un borrador y revisa el resultado.")
        instruction = st.text_area(
            "Objetivo de la sección",
            "Redacta una sección basada en la evidencia.",
            height=90,
        )
        if st.button(f"Generar borrador · {provider}", type="primary"):
            if fsm.state is not WorkflowState.DRAFTING:
                st.warning("Aprueba Parametrización y Curaduría antes de redactar.")
            elif not st.session_state.hits or not st.session_state.inspected_fragments.intersection(
                hit.document.document_id for hit in st.session_state.hits
            ):
                st.warning("Inspecciona al menos una evidencia recuperada antes de redactar.")
            else:
                try:
                    llm = create_llm_adapter(
                        provider, model=model, api_key=api_key, base_url=base_url
                    )
                    result = DraftingService(llm, store, budget_tokens=int(target_words)).draft(
                        instruction, query=st.session_state.get("query", "")
                    )
                    st.session_state.text = result.text
                    audit.record(
                        WorkflowState.DRAFTING, "LLM", "draft_generated",
                        {"provider": provider, "model": model, "text": result.text,
                         "citations": [h.document.metadata for h in result.citations]},
                        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                    )
                    st.success("Borrador generado y guardado en el expediente.")
                except (RuntimeError, ValueError) as exc:
                    st.error(str(exc))
        edited = st.text_area("Texto de trabajo", st.session_state.text, height=300)
        if edited != st.session_state.text:
            audit.record_human_edit(WorkflowState.DRAFTING, "HUMAN", st.session_state.text, edited)
            st.session_state.text = edited
        with st.expander("Revisión de gobernanza", expanded=bool(st.session_state.last_governance)):
            if st.button("Ejecutar controles de gobernanza"):
                gov = GovernanceService()
                l1 = gov.level1(st.session_state.text)
                l2 = gov.level2(st.session_state.text, st.session_state.hits)
                st.session_state.last_governance = (l1, l2)
            if st.session_state.last_governance:
                l1, l2 = st.session_state.last_governance
                st.write({"Nivel 1": {"hallazgos": l1.findings, "score": l1.score, "flag": l1.flagged},
                          "Nivel 2": {"score": l2.score, "semáforo": l2.flag}})
            else:
                st.info("Ejecuta los controles cuando el texto esté listo para revisión.")

    with evidence:
        st.subheader("Evidencia y documentos")
        st.caption("La búsqueda y la indexación se mantienen separadas para que el expediente sea fácil de revisar.")
        uploaded = st.file_uploader("Añadir PDF o texto", type=["pdf", "txt"], accept_multiple_files=True)
        if st.button("Indexar documentos") and uploaded:
            for item in uploaded:
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
                    st.error(str(exc))
            st.success(f"Indexación completada: {len(store.documents)} fragmentos disponibles.")
        st.session_state.query = st.text_input("Buscar en la evidencia", "método resultados")
        if st.button("Buscar evidencia") or st.session_state.query:
            st.session_state.hits = store.search(st.session_state.query, top_k=5)
        if not st.session_state.hits:
            st.info("Aún no hay resultados. Añade documentos y ejecuta una búsqueda.")
        for hit in st.session_state.hits:
            with st.expander(f"{hit.document.document_id} · relevancia {hit.score:.4f}"):
                st.caption(str(hit.document.metadata))
                st.write(hit.document.text)
                if st.button("Registrar inspección", key=f"inspect-{hit.document.document_id}"):
                    audit.inspect_evidence(WorkflowState.CURATION, "HUMAN", hit.document.document_id)
                    st.session_state.inspected_fragments.add(hit.document.document_id)
                    st.success("Inspección registrada en la trayectoria.")

    with record:
        st.subheader("Registro y transparencia")
        report_path = Path("data") / "trajectory.jsonl"
        if report_path.exists():
            report = transparency_report(report_path)
            st.json(report)
            col_json, col_md = st.columns(2)
            if col_json.button("Exportar reporte JSON"):
                export_report(report, Path("data") / "transparency.json")
                st.success("Reporte JSON exportado.")
            if col_md.button("Exportar reporte Markdown"):
                export_report(report, Path("data") / "transparency.md", "markdown")
                st.success("Reporte Markdown exportado.")
            events = audit.audit_port.list_events(project_id)
            if events:
                st.dataframe(
                    [{"timestamp": str(getattr(event, "timestamp", "")),
                      "fase": getattr(getattr(event, "phase", None), "value", ""),
                      "actor": getattr(event, "actor", ""),
                      "acción": getattr(event, "action_type", ""),
                      "hash": getattr(event, "event_hash", "")[:12]} for event in events],
                    use_container_width=True,
                )
        else:
            st.info("El registro aparecerá aquí después de la primera acción auditable.")

    st.markdown('<div class="marco-rule"></div>', unsafe_allow_html=True)
    st.subheader("Revisión humana y avance")
    next_phase = _next_phase(fsm.state)
    user, decision = st.columns([2, 1])
    signer = user.text_input("Persona responsable", "investigador")
    decision_value = decision.selectbox("Decisión", ["ACCEPTED", "AMENDED", "REJECTED"])
    action, rollback = st.columns([2, 1])
    if next_phase is None:
        action.success("El expediente está en fase de ensamblaje.")
    elif action.button(f"Firmar y avanzar a {_phase_name(next_phase)}", type="primary"):
        try:
            if fsm.state is WorkflowState.PARAMETRIZATION and not template.strip():
                raise InvalidStateTransitionError("Define la plantilla antes de continuar.")
            if fsm.state is WorkflowState.CURATION:
                if not store.documents:
                    raise InvalidStateTransitionError("Indexa el corpus antes de aprobar la Curaduría.")
                if not st.session_state.inspected_fragments:
                    raise InvalidStateTransitionError(
                        "Inspecciona al menos una evidencia antes de aprobar la Curaduría."
                    )
            if fsm.state is WorkflowState.DRAFTING:
                if not st.session_state.text.strip():
                    raise InvalidStateTransitionError("Guarda un borrador antes de ensamblar.")
                if st.session_state.last_governance is None:
                    raise InvalidStateTransitionError(
                        "Ejecuta los controles de gobernanza antes de ensamblar."
                    )
            signature = HumanSignature(
                user_id=signer, decision=decision_value,
                state_hash=f"{fsm.state.value}:{len(st.session_state.text)}",
            )
            fsm.transition(next_phase, {"human_signature": signature})
            audit.record(next_phase, signer, "transition_signed", {"decision": decision_value})
            st.success(f"Avance firmado: {_phase_name(next_phase)}.")
            st.rerun()
        except InvalidStateTransitionError as exc:
            st.error(str(exc))
    rollback_target = rollback.selectbox(
        "Retroceder a", [WorkflowState.PARAMETRIZATION, WorkflowState.CURATION, WorkflowState.DRAFTING],
        format_func=_phase_name,
    )
    if rollback.button("Firmar rollback"):
        events = audit.audit_port.list_events(project_id)
        if not events:
            st.warning("No hay eventos suficientes para registrar un rollback.")
        else:
            try:
                signature = HumanSignature(
                    user_id=signer, decision=decision_value,
                    state_hash=f"{fsm.state.value}:{len(st.session_state.text)}",
                )
                previous_state = fsm.state
                fsm.rollback(rollback_target, {"human_signature": signature})
                audit.rollback(previous_state, "HUMAN", events[-1].event_hash,
                               f"rollback firmado hacia {rollback_target.value}")
                st.success(f"Rollback aplicado: {_phase_name(previous_state)} → {_phase_name(rollback_target)}.")
                st.rerun()
            except InvalidStateTransitionError as exc:
                st.error(str(exc))


if __name__ == "__main__":
    main()
