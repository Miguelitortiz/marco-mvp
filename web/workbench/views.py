"""HTTP orchestration for the native MARCO interface.

The web layer owns request/session concerns only. Drafting, retrieval,
ingestion, governance, audit and workflow rules remain in ``core``.
"""
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from core.adapters import HybridRAGStore, JSONLAuditAdapter, PROVIDER_PRESETS, create_llm_adapter
from core.application import AuditService, DraftingService
from core.domain.configuration import load_governance_config
from core.domain.fsm import InvalidStateTransitionError, WorkflowFSM
from core.domain.models import HumanSignature, WorkflowState
from core.services.governance import GovernanceService
from core.services.ingestion import ingest_file
from core.services.transparency import transparency_report


PHASES = (
    (WorkflowState.PARAMETRIZATION, "Preparar", "Define alcance y presupuesto"),
    (WorkflowState.CURATION, "Curar", "Indexa y revisa evidencia"),
    (WorkflowState.DRAFTING, "Redactar", "Construye y revisa el texto"),
    (WorkflowState.ASSEMBLY, "Ensamblar", "Cierra el expediente auditable"),
)
_workbenches: dict[str, "Workbench"] = {}


@dataclass
class Workbench:
    fsm: WorkflowFSM = field(default_factory=lambda: WorkflowFSM(WorkflowState.PARAMETRIZATION))
    store: HybridRAGStore = field(default_factory=HybridRAGStore)
    text: str = ""
    hits: list[object] = field(default_factory=list)
    query: str = "método resultados"
    target_words: int = 500
    tolerance: float = 0.2
    template: str = "Sección experimental"
    provider: str = "Mock (offline)"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    last_governance: tuple[object, object] | None = None
    inspected_fragments: set[str] = field(default_factory=set)
    parametrized: bool = False

    @property
    def project_id(self) -> str:
        return "web-local"

    @property
    def audit(self) -> AuditService:
        return AuditService(JSONLAuditAdapter(Path("data") / "trajectory.jsonl"), self.project_id)

    @property
    def current_words(self) -> int:
        return len(self.text.split())

    def context(self) -> dict[str, object]:
        lower = int(self.target_words * (1 - self.tolerance))
        upper = int(self.target_words * (1 + self.tolerance))
        current_index = next(
            (index for index, (phase, _, _) in enumerate(PHASES)
             if phase is self.fsm.state), 0,
        )
        return {
            "workbench": self,
            "phases": PHASES,
            "current_phase_index": current_index,
            "current_phase_number": current_index + 1,
            "lower_bound": lower,
            "upper_bound": upper,
            "inspected_fragments": self.inspected_fragments,
            "providers": ["Mock (offline)", *PROVIDER_PRESETS],
            "report": transparency_report(Path("data") / "trajectory.jsonl")
            if Path("data") .joinpath("trajectory.jsonl").exists() else None,
        }


def _state(request: HttpRequest) -> Workbench:
    if not request.session.session_key:
        request.session.create()
    key = request.session.session_key
    return _workbenches.setdefault(key, Workbench())


def _fragment(request: HttpRequest, template: str, context: dict[str, object]) -> HttpResponse:
    return render(request, template, context)


def _workflow_redirect(request: HttpRequest) -> HttpResponse:
    """Reload the stage-specific screen after a state transition."""
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(status=204)
        response["HX-Redirect"] = "/"
        return response
    return render(request, "workbench/index.html", _state(request).context())


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "workbench/index.html", _state(request).context())


@require_POST
def search_evidence(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    workbench.query = request.POST.get("query", "").strip()
    workbench.hits = workbench.store.search(workbench.query, top_k=5) if workbench.query else []
    return _fragment(request, "workbench/_evidence.html", workbench.context())


@require_POST
def inspect_evidence(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    fragment_id = request.POST.get("fragment_id", "").strip()
    if fragment_id:
        workbench.inspected_fragments.add(fragment_id)
        workbench.audit.inspect_evidence(
            WorkflowState.CURATION, "HUMAN", fragment_id,
            request.POST.get("notes", "").strip(),
        )
    return _fragment(request, "workbench/_evidence.html", workbench.context())


@require_POST
def upload_documents(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    messages: list[str] = []
    upload_dir = Path("data") / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    for uploaded in request.FILES.getlist("documents"):
        path = upload_dir / Path(uploaded.name).name
        path.write_bytes(uploaded.read())
        try:
            documents = ingest_file(path)
            workbench.store.add(documents)
            workbench.audit.record(
                WorkflowState.CURATION, "HUMAN", "documents_indexed",
                {"source": uploaded.name, "chunks": len(documents)},
            )
            messages.append(f"{uploaded.name}: {len(documents)} fragmentos")
        except RuntimeError as exc:
            messages.append(str(exc))
    return _fragment(
        request, "workbench/_evidence.html",
        {**workbench.context(), "upload_messages": messages},
    )


@require_POST
def generate_draft(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    instruction = request.POST.get("instruction", "").strip()
    # Keep the service endpoint usable for API clients; the browser workflow
    # is enforced through its HTMX requests and phase controls.
    enforce_workflow = request.headers.get("HX-Request") == "true"
    if enforce_workflow and workbench.fsm.state is not WorkflowState.DRAFTING:
        return _fragment(
            request, "workbench/_editor.html",
            {**workbench.context(),
             "message": "La redacción está bloqueada hasta aprobar Parametrización y Curaduría."},
        )
    if enforce_workflow and (not workbench.hits or not workbench.inspected_fragments.intersection(
        hit.document.document_id for hit in workbench.hits
    )):
        return _fragment(
            request, "workbench/_editor.html",
            {**workbench.context(),
             "message": "Inspecciona al menos una evidencia recuperada antes de redactar."},
        )
    try:
        llm = create_llm_adapter(
            workbench.provider, model=workbench.model, api_key=workbench.api_key,
            base_url=workbench.base_url,
        )
        result = DraftingService(
            llm, workbench.store, budget_tokens=workbench.target_words,
        ).draft(instruction, query=workbench.query)
        workbench.text, workbench.hits = result.text, result.citations
        workbench.audit.record(
            WorkflowState.DRAFTING, "LLM", "draft_generated",
            {"provider": workbench.provider, "model": workbench.model, "text": result.text,
             "citations": [hit.document.metadata for hit in result.citations]},
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        )
        message = "Borrador generado y guardado en el expediente."
    except (RuntimeError, ValueError) as exc:
        message = str(exc)
    return _fragment(
        request, "workbench/_editor.html",
        {**workbench.context(), "message": message},
    )


@require_POST
def save_settings(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    workbench.template = request.POST.get("template", workbench.template).strip() or workbench.template
    try:
        workbench.target_words = max(50, int(request.POST.get("target_words", workbench.target_words)))
    except ValueError:
        pass
    workbench.provider = request.POST.get("provider", workbench.provider)
    preset = PROVIDER_PRESETS.get(workbench.provider, {})
    workbench.model = request.POST.get("model", "").strip() or preset.get("model", "")
    workbench.base_url = request.POST.get("base_url", "").strip() or preset.get("base_url", "")
    workbench.api_key = request.POST.get("api_key", "").strip()
    workbench.parametrized = True
    workbench.audit.record(
        WorkflowState.PARAMETRIZATION, "HUMAN", "constraints_configured",
        {"template": workbench.template, "target_words": workbench.target_words,
         "tolerance": workbench.tolerance},
    )
    return _fragment(
        request, "workbench/_notice.html",
        {**workbench.context(), "message": "Configuración guardada para esta sesión."},
    )


@require_POST
def save_text(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    updated = request.POST.get("text", "")
    if updated != workbench.text:
        workbench.audit.record_human_edit(
            WorkflowState.DRAFTING, "HUMAN", workbench.text, updated,
        )
        workbench.text = updated
    return _fragment(request, "workbench/_save_status.html", {"workbench": workbench})


@require_POST
def run_governance(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    workbench.text = request.POST.get("text", workbench.text)
    gov = GovernanceService()
    workbench.last_governance = (
        gov.level1(workbench.text), gov.level2(workbench.text, workbench.hits),
    )
    workbench.audit.record(
        WorkflowState.HUMAN_REVIEW, "SYSTEM", "governance_checked",
        {"level1_findings": workbench.last_governance[0].findings,
         "level1_score": workbench.last_governance[0].score,
         "level2_score": workbench.last_governance[1].score,
         "level2_flag": workbench.last_governance[1].flag},
    )
    return _fragment(request, "workbench/_governance.html", {"workbench": workbench})


def _signature(request: HttpRequest) -> HumanSignature:
    workbench = _state(request)
    return HumanSignature(
        user_id=request.POST.get("signer", "investigador"),
        decision=request.POST.get("decision", "ACCEPTED"),
        state_hash=f"{workbench.fsm.state.value}:{len(workbench.text)}",
    )


@require_POST
def advance_workflow(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    target = {
        WorkflowState.PARAMETRIZATION: WorkflowState.CURATION,
        WorkflowState.CURATION: WorkflowState.DRAFTING,
        WorkflowState.DRAFTING: WorkflowState.ASSEMBLY,
    }.get(workbench.fsm.state)
    message = "El expediente ya está en ensamblaje."
    if target:
        try:
            if workbench.fsm.state is WorkflowState.PARAMETRIZATION and not workbench.parametrized:
                raise InvalidStateTransitionError(
                    "Configura las restricciones del expediente antes de continuar."
                )
            if workbench.fsm.state is WorkflowState.CURATION:
                if not workbench.store.documents:
                    raise InvalidStateTransitionError(
                        "Indexa el corpus antes de aprobar la Curaduría."
                    )
                if not workbench.inspected_fragments:
                    raise InvalidStateTransitionError(
                        "Inspecciona al menos una evidencia antes de aprobar la Curaduría."
                    )
            if workbench.fsm.state is WorkflowState.DRAFTING:
                if not workbench.text.strip():
                    raise InvalidStateTransitionError("Guarda un borrador antes de ensamblar.")
                if workbench.last_governance is None:
                    raise InvalidStateTransitionError(
                        "Ejecuta los tres niveles de gobernanza antes de ensamblar."
                    )
            signature = _signature(request)
            workbench.fsm.transition(target, {"human_signature": signature})
            workbench.audit.record(
                target, signature.user_id, "transition_signed",
                {"decision": signature.decision},
            )
            message = f"Avance firmado: {target.value}."
        except InvalidStateTransitionError as exc:
            message = str(exc)
    if request.headers.get("HX-Request") == "true" and message.startswith("Avance firmado"):
        return _workflow_redirect(request)
    return _fragment(request, "workbench/_status.html", {**workbench.context(), "message": message})


@require_POST
def export_workflow(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    if workbench.fsm.state is not WorkflowState.ASSEMBLY:
        message = "El expediente debe estar en Ensamblaje antes de exportar."
    elif not workbench.last_governance:
        message = "Falta la revisión de gobernanza antes de exportar."
    else:
        report = transparency_report(Path("data") / "trajectory.jsonl")
        workbench.audit.record(
            WorkflowState.ASSEMBLY, "HUMAN", "exported",
            {"events": report.get("events", 0), "word_count": workbench.current_words},
        )
        message = "Expediente ensamblado y reporte de transparencia registrado."
    if request.headers.get("HX-Request") == "true" and message.startswith("Expediente ensamblado"):
        return _workflow_redirect(request)
    return _fragment(request, "workbench/_status.html", {**workbench.context(), "message": message})


@require_POST
def rollback_workflow(request: HttpRequest) -> HttpResponse:
    workbench = _state(request)
    target_name = request.POST.get("target", WorkflowState.PARAMETRIZATION.value)
    target = next((phase for phase, _, _ in PHASES if phase.value == target_name), None)
    events = workbench.audit.audit_port.list_events(workbench.project_id)
    try:
        if target is None or not events:
            raise InvalidStateTransitionError("No hay un destino o eventos para registrar el rollback.")
        previous = workbench.fsm.state
        workbench.fsm.rollback(target, {"human_signature": _signature(request)})
        workbench.audit.rollback(previous, "HUMAN", events[-1].event_hash,
                                 f"rollback firmado hacia {target.value}")
        message = f"Rollback aplicado: {previous.value} -> {target.value}."
    except InvalidStateTransitionError as exc:
        message = str(exc)
    if request.headers.get("HX-Request") == "true" and message.startswith("Rollback aplicado"):
        return _workflow_redirect(request)
    return _fragment(request, "workbench/_status.html", {**workbench.context(), "message": message})
