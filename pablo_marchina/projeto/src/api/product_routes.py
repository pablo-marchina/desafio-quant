"""Minimum persisted product routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.api.product_schemas import (
    ActionBriefJsonExportRead,
    ActionBriefRead,
    ActivationDossierGenerateResponse,
    ActivationDossierMarkdownRead,
    ActivationDossierRead,
    ActivationDossierSummaryRead,
    ActivationPlaybookListResponse,
    ActivationPlaybookRead,
    ActivationRecommendationListResponse,
    ActivationRecommendationRead,
    AnalysisEvidenceBundleRead,
    AnalysisRunCreate,
    AnalysisRunDetailResponse,
    AnalysisRunRead,
    AnalysisRunWorkflowRequest,
    AnalysisRunWorkflowResponse,
    ClaimListResponse,
    ClaimRead,
    ClaimReviewUpdate,
    DedupCandidateResponse,
    DependencyHealthRead,
    DiscoveryCandidateListResponse,
    DiscoveryCandidateRead,
    DiscoveryRunListResponse,
    DiscoveryRunRead,
    DiscoverySourceRead,
    EvidenceCoverageRead,
    ExportCreate,
    ExportRead,
    GenerateActivationRecommendationsResponse,
    ManualSeedRequest,
    ManualSeedResponse,
    SourceScraperRequest,
    SourceScraperResponse,
    OpportunityListItem,
    OpportunityListResponse,
    OpportunityScoreCreateResponse,
    OpportunityScoreRead,
    PersistedActionBriefRead,
    ProductCapabilityRead,
    ProductConfigurationItemRead,
    ProductHealthRead,
    ProductQualityMetricRead,
    ProductQualityRunRead,
    ProductQualitySummaryRead,
    ProductReadinessRead,
    ProductSetupChecklistItem,
    ProductSetupChecklistRead,
    PromoteCandidateResponse,
    RankedOpportunityListResponse,
    RankedOpportunityRead,
    ReadinessCheckRead,
    ReviewDecisionCreate,
    ReviewDecisionRead,
    StartupCreate,
    StartupEvidenceRead,
    StartupListItem,
    StartupRead,
    StartupUpdate,
    UrlListRequest,
    UrlListResponse,
    WorkflowReviewDecisionCreate,
)
from src.database.models import (
    ActionBriefRecord,
    ActivationDossierRecord,
    AnalysisRun,
    ClaimRecord,
    ProductQualityRun,
    Startup,
)
from src.database.session import get_db_session
from src.discovery.service import StartupDiscoveryService
from src.orchestration.service import WorkflowOrchestrationService
from src.quality.service import ProductQualityService
from src.repositories.product import ProductRepository
from src.repositories.workflow import WorkflowRepository
from src.services.product import ProductService
from src.services.product.activation_service import ActivationPlaybookService
from src.services.product.claim_ledger import ClaimLedgerService
from src.services.product.dossier_service import ActivationDossierService
from src.services.product.export_service import (
    persisted_action_brief_json_export_payload,
    persisted_action_brief_payload,
)
from src.services.product.opportunity_score_service import OpportunityScoreService
from src.services.product.readiness_gate import ReadinessGate
from src.services.product.readiness_service import ProductReadinessService

router = APIRouter(tags=["product"])
DbSession = Annotated[Session, Depends(get_db_session)]
ProductReady = Annotated[None, Depends(ReadinessGate())]

_CRITICAL_CLAIM_TYPES = {
    "gap_claim",
    "defensibility_claim",
    "nvidia_fit_claim",
    "production_readiness_claim",
}


def _startup_read(startup: Startup) -> StartupRead:
    return StartupRead(
        id=startup.id,
        name=startup.name,
        normalized_name=startup.normalized_name,
        website=startup.website,
        country=startup.country,
        sector=startup.sector,
        description=startup.description,
        product_summary=startup.product_summary,
        status=startup.status,
        tags=startup.tags_json,
        evidence=[
            StartupEvidenceRead(
                id=item.id,
                claim=item.claim,
                source_url=item.source_url,
                source_type=item.source_type,
                quote_or_evidence=item.quote_or_evidence,
                confidence=item.confidence,
                evidence_kind=item.evidence_kind,
                collected_at=item.collected_at,
                metadata=item.metadata_json,
            )
            for item in startup.evidence
        ],
        created_at=startup.created_at,
        updated_at=startup.updated_at,
    )


def _analysis_run_read(run: AnalysisRun) -> AnalysisRunRead:
    latest_brief = max(run.briefs, key=lambda item: item.version, default=None)
    return AnalysisRunRead(
        id=run.id,
        startup_id=run.startup_id,
        status=run.status,
        error_message=run.error_message,
        degraded_reason=run.degraded_reason,
        started_at=run.started_at,
        completed_at=run.completed_at,
        pipeline_version=run.pipeline_version,
        corpus_version=run.corpus_version,
        input_snapshot=run.input_snapshot_json,
        output_snapshot=run.output_snapshot_json,
        scores=[
            {
                "id": item.id,
                "score_type": item.score_type,
                "value": item.value,
                "confidence": item.confidence,
                "components": item.components_json,
                "missing_evidence": item.missing_evidence_json,
            }
            for item in run.scores
        ],
        gaps=[
            {
                "id": item.id,
                "gap_type": item.gap_type,
                "detected": item.detected,
                "confidence": item.confidence,
                "evidence_tag": item.evidence_tag,
                "reasoning": item.reasoning,
                "evidence_refs": item.evidence_refs_json,
                "missing_evidence": item.missing_evidence_json,
            }
            for item in run.gaps
        ],
        nvidia_mappings=[
            {
                "id": item.id,
                "gap_record_id": item.gap_record_id,
                "technology_name": item.technology_name,
                "addresses_gap": item.addresses_gap,
                "justification": item.justification,
                "recommendation_action": item.recommendation_action,
                "priority": item.priority,
                "details": item.details_json,
            }
            for item in run.mappings
        ],
        readiness_checks=[
            ReadinessCheckRead(
                code=item.code,
                severity=item.severity,
                status=item.status,
                user_message=item.user_message,
                internal_detail=item.internal_detail,
                recommended_action=item.recommended_action,
                metadata=item.metadata_json,
                observed_at=item.observed_at,
            )
            for item in run.readiness_checks
        ],
        action_brief_id=latest_brief.id if latest_brief is not None else None,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _build_workflow_response(
    state_analysis_run_id: str | None,
    startup_id: str,
    session: Session,
    *,
    workflow_state_status: str = "",
    blockers: list[str] | None = None,
) -> AnalysisRunWorkflowResponse:
    executed: list[str] = []
    review_required = False
    if state_analysis_run_id:
        try:
            wf_repo = WorkflowRepository(session)
            wf_run = wf_repo.get_workflow_for_analysis_run(state_analysis_run_id)
            if wf_run and wf_run.state_json:
                sd = wf_run.state_json
                executed = list(
                    dict.fromkeys(
                        sd.get("completed_nodes", []) + sd.get("failed_nodes", []) + sd.get("degraded_nodes", [])
                    )
                )
                review_required = sd.get("review_required", False)
                if not blockers:
                    blockers = sd.get("blockers", [])
        except Exception:
            pass
    quality_val: dict[str, Any] = {}
    if state_analysis_run_id:
        try:
            qs = ProductQualityService(session)
            summ = qs.summarize_quality_result(state_analysis_run_id)
            if summ:
                quality_val = dict(summ)
        except Exception:
            pass
    quality = quality_val
    action_brief: ActionBriefRead | None = None
    evidence_validation: dict[str, Any] = {}
    rag_metrics: dict[str, Any] = {}
    recommendation_metrics: dict[str, Any] = {}
    brief_metrics: dict[str, Any] = {}
    if state_analysis_run_id:
        try:
            repo = ProductRepository(session)
            br = repo.get_latest_action_brief(state_analysis_run_id)
            if br:
                action_brief = _action_brief_read(br)
        except Exception:
            pass
        try:
            run = repo.get_analysis_run(state_analysis_run_id)
            if run:
                output = run.output_snapshot_json or {}
                evidence_validation = output.get("validated_evidence", {})
                rag_metrics = output.get("rag_output", {})
                recommendation_metrics = output.get("recommendation", {})
                raw_brief_metrics = output.get("brief_metrics")
                brief_metrics = (
                    raw_brief_metrics if isinstance(raw_brief_metrics, dict) else output.get("action_brief", {})
                )
        except Exception:
            pass
    status_val = workflow_state_status or "completed"
    return AnalysisRunWorkflowResponse(
        run_id=state_analysis_run_id or "",
        startup_id=startup_id,
        status=status_val,
        review_required=review_required,
        executed_nodes=executed,
        blockers=blockers or [],
        quality=quality,
        evidence_validation=evidence_validation,
        rag_metrics=rag_metrics,
        recommendation_metrics=recommendation_metrics,
        brief_metrics=brief_metrics,
        action_brief=action_brief,
    )


def _build_detail_response(analysis_run_id: str, session: Session) -> AnalysisRunDetailResponse:
    svc = ProductService(session)
    run = svc.get_analysis_run(analysis_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    executed: list[str] = []
    blockers: list[str] = []
    review_required = False
    review_payload: dict[str, Any] | None = None
    try:
        wf_repo = WorkflowRepository(session)
        wf_run = wf_repo.get_workflow_for_analysis_run(analysis_run_id)
        if wf_run and wf_run.state_json:
            sd = wf_run.state_json
            executed = list(
                dict.fromkeys(sd.get("completed_nodes", []) + sd.get("failed_nodes", []) + sd.get("degraded_nodes", []))
            )
            blockers = sd.get("blockers", [])
            review_required = sd.get("review_required", False)
            review_payload = sd.get("review_payload")
    except Exception:
        pass
    quality_res: dict[str, Any] = {}
    try:
        qs = ProductQualityService(session)
        summ = qs.summarize_quality_result(analysis_run_id)
        if summ:
            quality_res = dict(summ)
    except Exception:
        pass
    quality = quality_res
    output = run.output_snapshot_json or {}
    evidence_validation = output.get("validated_evidence", {})
    rag_metrics = output.get("rag_output", {})
    recommendation_metrics = output.get("recommendation", {})
    raw_brief_metrics = output.get("brief_metrics")
    brief_metrics = raw_brief_metrics if isinstance(raw_brief_metrics, dict) else output.get("action_brief", {})
    if isinstance(rag_metrics, dict):
        pass
    else:
        rag_metrics = {}
    action_brief: ActionBriefRead | None = None
    try:
        brief_record = svc.repository.get_latest_action_brief(analysis_run_id)
        if brief_record:
            action_brief = _action_brief_read(brief_record)
    except Exception:
        pass
    dossier_summary: ActivationDossierSummaryRead | None = None
    try:
        dossier_svc = ActivationDossierService(session)
        dossier_summary = ActivationDossierSummaryRead(**dossier_svc.get_dossier_summary(analysis_run_id))
    except Exception:
        dossier_summary = None
    return AnalysisRunDetailResponse(
        run_id=run.id,
        startup_id=run.startup_id,
        status=run.status,
        executed_nodes=executed,
        blockers=blockers,
        quality=quality,
        evidence_validation=evidence_validation if isinstance(evidence_validation, dict) else {},
        rag_metrics=rag_metrics if isinstance(rag_metrics, dict) else {},
        recommendation_metrics=(recommendation_metrics if isinstance(recommendation_metrics, dict) else {}),
        brief_metrics=brief_metrics if isinstance(brief_metrics, dict) else {},
        action_brief=action_brief,
        dossier_summary=dossier_summary,
        review_required=review_required,
        review_payload=review_payload,
    )


def _inject_claim_summary(result: AnalysisRunRead, session: Session) -> None:
    try:
        from src.api.product_schemas import ClaimSummaryRead
        from src.repositories.claim import ClaimRepository

        repo = ClaimRepository(session)
        cov = repo.get_evidence_coverage_summary(result.id)
        if cov["total_claims"] > 0:
            result.claim_summary = ClaimSummaryRead(
                total_claims=cov["total_claims"],
                supported_claims=cov["supported_claims"],
                unsupported_claims=cov["unsupported_claims"],
                evidence_coverage=cov["evidence_coverage"],
            )
    except Exception:
        result.claim_summary = None


def _inject_dossier_summary(result: AnalysisRunRead, session: Session) -> None:
    try:
        from src.api.product_schemas import ActivationDossierSummaryRead
        from src.services.product.dossier_service import ActivationDossierService

        svc = ActivationDossierService(session)
        summary = svc.get_dossier_summary(result.id)
        result.dossier_summary = ActivationDossierSummaryRead(**summary)
    except Exception:
        result.dossier_summary = None


def _action_brief_read(record: ActionBriefRecord) -> ActionBriefRead:
    return ActionBriefRead(
        id=record.id,
        analysis_run_id=record.analysis_run_id,
        version=record.version,
        schema_version=record.schema_version,
        brief_json=record.brief_json,
        brief_markdown=record.brief_markdown,
        is_latest=record.is_latest,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _persisted_action_brief_read(
    run: AnalysisRun,
    record: ActionBriefRecord,
) -> PersistedActionBriefRead:
    try:
        return PersistedActionBriefRead(**persisted_action_brief_payload(run, record))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persisted action brief is not compatible with the quantitative schema.",
        ) from exc


@router.post("/startups", response_model=StartupRead, status_code=status.HTTP_201_CREATED)
def create_startup(
    request: StartupCreate,
    _gate: ProductReady,
    session: DbSession,
) -> StartupRead:
    service = ProductService(session)
    payload = request.model_dump(mode="python")
    try:
        startup = service.create_startup(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _startup_read(startup)


@router.get("/startups", response_model=list[StartupListItem])
def list_startups(
    session: DbSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[StartupListItem]:
    service = ProductService(session)
    response: list[StartupListItem] = []
    for startup in service.list_startups(offset=offset, limit=limit):
        latest = service.repository.get_latest_analysis_run(startup.id)
        response.append(
            StartupListItem(
                id=startup.id,
                name=startup.name,
                website=startup.website,
                sector=startup.sector,
                status=startup.status,
                latest_analysis_run_id=latest.id if latest is not None else None,
                latest_analysis_status=latest.status if latest is not None else None,
                created_at=startup.created_at,
                updated_at=startup.updated_at,
            )
        )
    return response


@router.get("/startups/{startup_id}", response_model=StartupRead)
def get_startup(startup_id: str, session: DbSession) -> StartupRead:
    startup = ProductService(session).get_startup(startup_id)
    if startup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Startup not found.")
    return _startup_read(startup)


@router.post(
    "/analysis-runs",
    response_model=AnalysisRunWorkflowResponse,
    status_code=status.HTTP_200_OK,
)
def create_analysis_run_workflow(
    request: AnalysisRunWorkflowRequest,
    session: DbSession,
) -> AnalysisRunWorkflowResponse:
    startup_id = request.startup_id
    svc = ProductService(session)
    startup = svc.get_startup(startup_id)
    if startup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Startup not found.")
    readiness = ProductReadinessService().get_product_readiness()
    if not readiness.ready:
        msgs: list[str] = []
        for m in readiness.user_messages or []:
            if isinstance(m, dict):
                msgs.append(m.get("reason", str(m)))
            else:
                msgs.append(str(m))
        return AnalysisRunWorkflowResponse(
            run_id="",
            startup_id=startup_id,
            status="blocked",
            blockers=msgs,
        )
    try:
        orch = WorkflowOrchestrationService(session)
        state = orch.create_and_run_workflow(
            startup_id=startup_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis run failed.",
        ) from exc
    return _build_workflow_response(
        state.analysis_run_id,
        startup_id,
        session,
        workflow_state_status=state.status or "completed",
        blockers=state.blockers,
    )


@router.post(
    "/startups/{startup_id}/analysis-runs",
    response_model=AnalysisRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis_run(
    startup_id: str,
    request: AnalysisRunCreate,
    _gate: ProductReady,
    session: DbSession,
) -> AnalysisRunRead:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Legacy analysis creation is disabled. Use POST /workflows/product-runs "
            "so the single LangGraph pipeline with mandatory RAG is always used."
        ),
    )


@router.get("/analysis-runs/{analysis_run_id}", response_model=AnalysisRunDetailResponse)
def get_analysis_run(analysis_run_id: str, session: DbSession) -> AnalysisRunDetailResponse:
    return _build_detail_response(analysis_run_id, session)


@router.get("/analysis-runs/{analysis_run_id}/brief", response_model=PersistedActionBriefRead)
def get_action_brief(analysis_run_id: str, session: DbSession) -> PersistedActionBriefRead:
    service = ProductService(session)
    run = service.get_analysis_run(analysis_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    brief = service.get_action_brief_for_run(analysis_run_id)
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action brief not found.")
    return _persisted_action_brief_read(run, brief)


@router.get(
    "/analysis-runs/{analysis_run_id}/brief/export/json",
    response_model=ActionBriefJsonExportRead,
)
def export_action_brief_json(
    analysis_run_id: str,
    session: DbSession,
) -> ActionBriefJsonExportRead:
    service = ProductService(session)
    run = service.get_analysis_run(analysis_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    brief = service.get_action_brief_for_run(analysis_run_id)
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action brief not found.")
    try:
        return ActionBriefJsonExportRead(**persisted_action_brief_json_export_payload(run, brief))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persisted action brief is not compatible with the quantitative schema.",
        ) from exc


@router.get("/health/product", response_model=ProductHealthRead)
def product_health(session: DbSession) -> ProductHealthRead:
    return ProductHealthRead(**ProductService(session).get_product_health())


@router.get("/health/dependencies", response_model=DependencyHealthRead)
def dependency_health(session: DbSession) -> DependencyHealthRead:
    data: dict[str, Any] = ProductService(session).get_dependency_health()
    return DependencyHealthRead(**data)


@router.patch("/startups/{startup_id}", response_model=StartupRead)
def update_startup(
    startup_id: str,
    request: StartupUpdate,
    _gate: ProductReady,
    session: DbSession,
) -> StartupRead:
    service = ProductService(session)
    fields = request.model_dump(exclude_unset=True)
    if not fields:
        startup = service.get_startup(startup_id)
        if startup is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Startup not found.")
        return _startup_read(startup)
    try:
        updated = service.update_startup(startup_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _startup_read(updated)


@router.post(
    "/analysis-runs/{analysis_run_id}/review",
    response_model=ReviewDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    analysis_run_id: str,
    request: ReviewDecisionCreate,
    _gate: ProductReady,
    session: DbSession,
) -> ReviewDecisionRead:
    service = ProductService(session)
    try:
        record = service.create_review(
            analysis_run_id,
            decision=request.decision,
            reviewer=request.reviewer,
            notes=request.notes,
            metadata=request.metadata,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ReviewDecisionRead(
        id=record.id,
        analysis_run_id=record.analysis_run_id,
        startup_id=record.startup_id,
        decision=record.decision,
        reviewer=record.reviewer,
        notes=record.notes,
        thread_id=record.thread_id,
        review_payload_snapshot=record.review_payload_snapshot,
        status_before_resume=record.status_before_resume,
        status_after_resume=record.status_after_resume,
        metadata=record.metadata_json,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post(
    "/analysis-runs/{analysis_run_id}/resume",
    response_model=AnalysisRunWorkflowResponse,
    status_code=status.HTTP_200_OK,
)
def resume_analysis_run(
    analysis_run_id: str,
    body: WorkflowReviewDecisionCreate,
    session: DbSession,
) -> AnalysisRunWorkflowResponse:
    """Resume an analysis run workflow that is awaiting human review.

    Persists a ReviewDecision as an audit record, then resumes the
    LangGraph workflow from its interrupt point.  The graph
    checkpointer must have been cached from the initial run.
    """
    svc = ProductService(session)
    run = svc.get_analysis_run(analysis_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run not found: {analysis_run_id}",
        )
    wf_repo = WorkflowRepository(session)
    wf_run = wf_repo.get_workflow_for_analysis_run(analysis_run_id)
    if wf_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No workflow found for analysis run: {analysis_run_id}",
        )

    status_before = wf_run.status
    thread_id: str | None = None
    review_payload: dict | None = None
    if wf_run.state_json:
        meta = wf_run.state_json.get("metadata_json") or {}
        thread_id = meta.get("_langgraph_thread_id")
        review_payload = wf_run.state_json.get("review_payload")

    from src.repositories.review import ReviewDecisionRepository

    review_repo = ReviewDecisionRepository(session)
    try:
        review_record = review_repo.create(
            analysis_run_id=analysis_run_id,
            startup_id=run.startup_id,
            decision=body.decision,
            reviewer=body.reviewer,
            notes=body.notes,
            thread_id=thread_id,
            review_payload_snapshot=review_payload,
            status_before_resume=status_before,
        )
        session.flush()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist review decision.",
        ) from exc

    try:
        orch = WorkflowOrchestrationService(session)
        orch.submit_review(
            wf_run.id,
            decision=body.decision,
            reviewer=body.reviewer,
            notes=body.notes,
            resume=True,
        )
    except (LookupError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    wf_run_after = wf_repo.get_workflow_run(wf_run.id)
    if wf_run_after is not None:
        review_repo.update_status_after_resume(
            review_record.id,
            status_after_resume=wf_run_after.status,
        )
        session.commit()

    return _build_workflow_response(
        analysis_run_id,
        run.startup_id,
        session,
    )


@router.get(
    "/analysis-runs/{analysis_run_id}/reviews",
    response_model=list[ReviewDecisionRead],
)
def list_reviews(analysis_run_id: str, session: DbSession) -> list[ReviewDecisionRead]:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    records = service.list_reviews(analysis_run_id)
    return [
        ReviewDecisionRead(
            id=item.id,
            analysis_run_id=item.analysis_run_id,
            startup_id=item.startup_id,
            decision=item.decision,
            reviewer=item.reviewer,
            notes=item.notes,
            thread_id=item.thread_id,
            review_payload_snapshot=item.review_payload_snapshot,
            status_before_resume=item.status_before_resume,
            status_after_resume=item.status_after_resume,
            metadata=item.metadata_json,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in records
    ]


@router.get("/opportunities", response_model=OpportunityListResponse)
def list_opportunities(
    session: DbSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    recommended_motion: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    sector: str | None = Query(default=None),
    has_degraded: bool | None = Query(default=None),
    review_decision: str | None = Query(default=None),
    order_by: str = Query(default="inception_fit_score"),
) -> OpportunityListResponse:
    service = ProductService(session)
    items, total = service.list_opportunities(
        offset=offset,
        limit=limit,
        status=status,
        recommended_motion=recommended_motion,
        min_score=min_score,
        sector=sector,
        has_degraded=has_degraded,
        review_decision=review_decision,
        order_by=order_by,
    )
    run_ids: list[str] = [item["latest_analysis_run_id"] for item in items if item.get("latest_analysis_run_id")]
    if run_ids:
        try:
            act_service = ActivationPlaybookService(session)
            top_by_run = act_service.get_top_by_run_ids(run_ids)
            for item in items:
                run_id = item.get("latest_analysis_run_id")
                if run_id and run_id in top_by_run:
                    top = top_by_run[run_id]
                    item["top_activation_playbook"] = top.get("playbook_name")
                    item["activation_confidence"] = top.get("confidence")
                    item["activation_next_step"] = top.get("next_step")
                    exp = top.get("technical_experiment", "")
                    item["technical_experiment_summary"] = exp[:150] if exp else None
        except Exception:
            pass
        try:
            dossier_svc = ActivationDossierService(session)
            for item in items:
                run_id = item.get("latest_analysis_run_id")
                if run_id:
                    summary = dossier_svc.get_dossier_summary(run_id)
                    item["dossier_available"] = summary.get("dossier_available", False)
                    item["latest_dossier_id"] = summary.get("dossier_id")
        except Exception:
            pass
    return OpportunityListResponse(
        items=[OpportunityListItem(**item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/analysis-runs/{analysis_run_id}/opportunity-score",
    response_model=OpportunityScoreCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def compute_opportunity_score(
    analysis_run_id: str,
    _gate: ProductReady,
    session: DbSession,
) -> OpportunityScoreCreateResponse:
    service = OpportunityScoreService(session)
    try:
        result = service.compute_score(analysis_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    from src.api.product_schemas import (
        OpportunityScoreComponentRead,
        OpportunityScoreExplainRead,
        OpportunityScorePenaltyRead,
    )

    components = result.get("components", {})
    explanation = OpportunityScoreExplainRead(
        components=[
            OpportunityScoreComponentRead(name=name, value=val, weight=0.0) for name, val in components.items()
        ],
        missing_components=[name for name, val in components.items() if val is None],
        penalties=[
            OpportunityScorePenaltyRead(type=p["type"], value=p["value"], detail=p["detail"])
            for p in (result.get("penalties") or [])
        ],
        penalty_total=result.get("penalty_total", 0.0),
        formula_summary=(f"base_score - penalties = {result.get('opportunity_score', 0):.4f}"),
    )

    return OpportunityScoreCreateResponse(
        analysis_run_id=analysis_run_id,
        opportunity_score=result.get("opportunity_score", 0.0),
        score_tier=result.get("score_tier", "low"),
        evidence_ref_count=result.get("evidence_ref_count", 0),
        recommended_action=result.get("recommended_action", ""),
        reasoning=result.get("reasoning", ""),
        explanation=explanation,
    )


@router.get(
    "/analysis-runs/{analysis_run_id}/opportunity-score",
    response_model=OpportunityScoreRead,
)
def get_opportunity_score(
    analysis_run_id: str,
    session: DbSession,
) -> OpportunityScoreRead:
    service = OpportunityScoreService(session)
    result = service.get_latest_score(analysis_run_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No opportunity score found for this analysis run",
        )
    return OpportunityScoreRead(
        id=result["id"],
        analysis_run_id=result["analysis_run_id"],
        score_version=result["score_version"],
        opportunity_score=result["opportunity_score"],
        score_tier=result["score_tier"],
        components=result["components"],
        penalties=result["penalties"],
        penalty_total=result["penalty_total"],
        evidence_refs=result["evidence_refs"],
        recommended_action=result["recommended_action"],
        reasoning=result["reasoning"],
        created_at=result["created_at"],
        updated_at=result["updated_at"],
    )


@router.get(
    "/opportunities/ranked",
    response_model=RankedOpportunityListResponse,
)
def list_ranked_opportunities(
    session: DbSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    min_score: float | None = Query(default=None, ge=0, le=1),
    tier: str | None = Query(default=None),
    recommended_action: str | None = Query(default=None),
) -> RankedOpportunityListResponse:
    service = OpportunityScoreService(session)
    items, total = service.list_ranked_opportunities(
        offset=offset,
        limit=limit,
        min_score=min_score,
        tier=tier,
        recommended_action=recommended_action,
    )
    return RankedOpportunityListResponse(
        items=[RankedOpportunityRead(**item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


def _read_export_content_for_api(record: Any) -> str | dict[str, Any] | None:
    """Read generated export content for UI delivery.

    The persisted storage path is relative to PRODUCT_DATA_DIR. Returning the
    content through the API lets the frontend complete the final delivery flow
    without shelling out to curl or reading server files directly.
    """
    import json
    import os
    from pathlib import Path

    if not record.storage_path or record.status != "completed":
        return None
    base = Path(os.getenv("PRODUCT_DATA_DIR", "data/product")).resolve()
    path = (base / record.storage_path).resolve()
    if not str(path).startswith(str(base)) or not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if record.export_type == "json":
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


@router.post(
    "/analysis-runs/{analysis_run_id}/exports",
    response_model=ExportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_export(
    analysis_run_id: str,
    request: ExportCreate,
    _gate: ProductReady,
    session: DbSession,
) -> ExportRead:
    service = ProductService(session)
    try:
        record = service.create_export(analysis_run_id, request.export_type)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ExportRead(
        id=record.id,
        analysis_run_id=record.analysis_run_id,
        action_brief_id=record.action_brief_id,
        export_type=record.export_type,
        status=record.status,
        storage_path=record.storage_path,
        content_hash=record.content_hash,
        error_message=record.error_message,
        content=_read_export_content_for_api(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/exports/{export_id}", response_model=ExportRead)
def get_export(export_id: str, session: DbSession) -> ExportRead:
    service = ProductService(session)
    record = service.get_export(export_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found.")
    return ExportRead(
        id=record.id,
        analysis_run_id=record.analysis_run_id,
        action_brief_id=record.action_brief_id,
        export_type=record.export_type,
        status=record.status,
        storage_path=record.storage_path,
        content_hash=record.content_hash,
        error_message=record.error_message,
        content=_read_export_content_for_api(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _claim_read(record: ClaimRecord) -> ClaimRead:
    return ClaimRead(
        id=record.id,
        startup_id=record.startup_id,
        analysis_run_id=record.analysis_run_id,
        claim_text=record.claim_text,
        claim_type=record.claim_type,
        support_level=record.support_level,
        confidence=record.confidence,
        evidence_refs=record.evidence_refs_json,
        used_in_score=record.used_in_score,
        used_in_gap=record.used_in_gap,
        used_in_mapping=record.used_in_mapping,
        used_in_brief=record.used_in_brief,
        review_status=record.review_status,
        reviewer_notes=record.reviewer_notes,
        metadata=record.metadata_json,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/analysis-runs/{analysis_run_id}/claims", response_model=ClaimListResponse)
def list_claims(
    analysis_run_id: str,
    session: DbSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    claim_type: str | None = Query(default=None),
    support_level: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
) -> ClaimListResponse:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    ledger = ClaimLedgerService(session)
    records = ledger.get_claims_for_analysis_run(
        analysis_run_id,
        claim_type=claim_type,
        support_level=support_level,
        review_status=review_status,
    )
    page = records[offset : offset + limit]
    return ClaimListResponse(
        items=[_claim_read(r) for r in page],
        total=len(records),
        offset=offset,
        limit=limit,
    )


@router.get(
    "/analysis-runs/{analysis_run_id}/evidence-coverage",
    response_model=EvidenceCoverageRead,
)
def get_evidence_coverage(
    analysis_run_id: str,
    session: DbSession,
) -> EvidenceCoverageRead:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    ledger = ClaimLedgerService(session)
    coverage = ledger.get_evidence_coverage_for_analysis_run(analysis_run_id)
    return EvidenceCoverageRead(**coverage)


def _readiness_check_read(item: Any) -> ReadinessCheckRead:
    return ReadinessCheckRead(
        code=item.code,
        severity=item.severity,
        status=item.status,
        user_message=item.user_message,
        internal_detail=item.internal_detail,
        recommended_action=item.recommended_action,
        metadata=item.metadata_json,
        observed_at=item.observed_at,
    )


def _group_claims(claims: list[ClaimRead]) -> dict[str, list[ClaimRead]]:
    grouped: dict[str, list[ClaimRead]] = {
        "supported": [],
        "weak": [],
        "unsupported": [],
        "critical": [],
    }
    for claim in claims:
        if claim.support_level == "unsupported":
            grouped["unsupported"].append(claim)
        elif claim.support_level == "weak":
            grouped["weak"].append(claim)
        else:
            grouped["supported"].append(claim)

        if (
            claim.claim_type in _CRITICAL_CLAIM_TYPES
            or claim.used_in_score
            or claim.used_in_gap
            or claim.used_in_mapping
            or claim.used_in_brief
        ):
            grouped["critical"].append(claim)
    return grouped


def _bundle_confidence(coverage: EvidenceCoverageRead, degraded_count: int) -> str:
    if coverage.total_claims <= 0:
        return "unknown"
    if coverage.evidence_coverage >= 0.75 and coverage.unsupported_claims == 0 and degraded_count == 0:
        return "high"
    if coverage.evidence_coverage >= 0.4 and coverage.unsupported_claim_rate < 0.5:
        return "medium"
    return "low"


def _bundle_readiness(run: AnalysisRun, degraded_checks: list[ReadinessCheckRead]) -> str:
    if run.status == "failed":
        return "failed"
    if any(check.status == "error" for check in degraded_checks):
        return "blocked"
    if run.status == "degraded" or degraded_checks:
        return "degraded"
    if run.status == "completed":
        return "ready"
    return run.status


def _collect_missing_evidence(
    run: AnalysisRun,
    claims: list[ClaimRead],
    degraded_checks: list[ReadinessCheckRead],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for claim in claims:
        if claim.support_level in {"unsupported", "weak"}:
            missing.append(
                {
                    "type": "claim",
                    "claim_id": claim.id,
                    "claim_type": claim.claim_type,
                    "support_level": claim.support_level,
                    "claim_text": claim.claim_text,
                    "recommended_action": "Collect stronger public evidence before treating this as proven.",
                }
            )

    for score in run.scores:
        if score.missing_evidence_json:
            missing.append(
                {
                    "type": "score",
                    "score_type": score.score_type,
                    "missing_evidence": score.missing_evidence_json,
                }
            )

    for gap in run.gaps:
        if gap.missing_evidence_json:
            missing.append(
                {
                    "type": "gap",
                    "gap_type": gap.gap_type,
                    "missing_evidence": gap.missing_evidence_json,
                }
            )

    for check in degraded_checks:
        if check.recommended_action:
            missing.append(
                {
                    "type": "readiness_check",
                    "code": check.code,
                    "status": check.status,
                    "recommended_action": check.recommended_action,
                }
            )
    return missing


def _collect_contradictions(
    claims: list[ClaimRead],
    readiness_checks: list[ReadinessCheckRead],
) -> list[dict[str, Any]]:
    contradictions: list[dict[str, Any]] = []
    for claim in claims:
        if claim.review_status == "rejected":
            contradictions.append(
                {
                    "type": "rejected_claim",
                    "claim_id": claim.id,
                    "claim_text": claim.claim_text,
                    "reviewer_notes": claim.reviewer_notes,
                }
            )
    for check in readiness_checks:
        if "contradiction" in check.code.lower() or "contradiction" in check.user_message.lower():
            contradictions.append(
                {
                    "type": "readiness_check",
                    "code": check.code,
                    "message": check.user_message,
                }
            )
    return contradictions


def _rag_support_summary(
    run: AnalysisRun,
    claims: list[ClaimRead],
    recommendations: list[ActivationRecommendationRead],
) -> dict[str, Any]:
    output_snapshot = run.output_snapshot_json or {}
    readiness_codes = {check.code for check in run.readiness_checks}
    supporting_refs = sum(len(claim.evidence_refs) for claim in claims)
    supporting_refs += sum(len(rec.evidence_refs) for rec in recommendations)
    rag_metrics = output_snapshot.get("rag_metrics") or output_snapshot.get("rag_summary") or {}
    rag_degraded_codes = sorted(code for code in readiness_codes if "RAG" in code or "QDRANT" in code)
    rag_available = not any(
        check.code in rag_degraded_codes and check.status in {"degraded", "error"} for check in run.readiness_checks
    )
    return {
        "required": True,
        "backend": output_snapshot.get("rag_backend") or "qdrant",
        "available": rag_available,
        "supporting_refs_count": supporting_refs,
        "metrics": rag_metrics if isinstance(rag_metrics, dict) else {"summary": rag_metrics},
        "degraded_codes": rag_degraded_codes,
    }


def _alternatives_lost(
    run: AnalysisRun,
    recommendations: list[ActivationRecommendationRead],
) -> list[dict[str, Any]]:
    promoted_ids = {rec.playbook_id for rec in recommendations}
    detected_gaps = {gap.gap_type for gap in run.gaps if gap.detected}
    alternatives: list[dict[str, Any]] = []
    for playbook in ActivationPlaybookService.get_playbooks():
        if playbook.playbook_id in promoted_ids:
            continue
        matched_gaps = [gap for gap in playbook.target_gap_types if gap in detected_gaps]
        reason = (
            "Matched persisted gaps, but was not promoted by the persisted recommendation set."
            if matched_gaps
            else "No detected persisted gap matched this playbook."
        )
        alternatives.append(
            {
                "playbook_id": playbook.playbook_id,
                "playbook_name": playbook.name,
                "matched_gap_types": matched_gaps,
                "nvidia_technologies": playbook.nvidia_technologies,
                "reason_lost": reason,
                "evidence_needed": playbook.evidence_requirements,
            }
        )
    return alternatives


def _analysis_evidence_bundle_read(run: AnalysisRun, session: Session) -> AnalysisEvidenceBundleRead:
    ledger = ClaimLedgerService(session)
    coverage = EvidenceCoverageRead(**ledger.get_evidence_coverage_for_analysis_run(run.id))
    claims = [_claim_read(record) for record in ledger.get_claims_for_analysis_run(run.id)]
    grouped_claims = _group_claims(claims)
    readiness_checks = [_readiness_check_read(item) for item in run.readiness_checks]
    degraded_checks = [check for check in readiness_checks if check.status in {"degraded", "error"}]

    act_service = ActivationPlaybookService(session)
    recommendations = [_activation_rec_read(record) for record in act_service.get_recommendations_for_run(run.id)]

    dossier_record = ActivationDossierService(session).get_latest_dossier(run.id)
    dossier = _dossier_read(dossier_record) if dossier_record is not None else None

    latest_observed_at = max((check.observed_at for check in readiness_checks), default=run.updated_at)
    latest_brief = max(run.briefs, key=lambda item: item.version, default=None)
    return AnalysisEvidenceBundleRead(
        analysis_run_id=run.id,
        startup_id=run.startup_id,
        status=run.status,
        readiness=_bundle_readiness(run, degraded_checks),
        confidence=_bundle_confidence(coverage, len(degraded_checks)),
        evidence_coverage=coverage,
        claims=grouped_claims,
        recommendations=recommendations,
        dossier=dossier,
        readiness_checks=readiness_checks,
        missing_evidence=_collect_missing_evidence(run, claims, degraded_checks),
        contradictions=_collect_contradictions(claims, readiness_checks),
        degraded_checks=degraded_checks,
        rag_support=_rag_support_summary(run, claims, recommendations),
        trust_freshness={
            "pipeline_version": run.pipeline_version,
            "corpus_version": run.corpus_version,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "latest_readiness_check_at": latest_observed_at.isoformat() if latest_observed_at else None,
            "evidence_coverage": coverage.evidence_coverage,
            "avg_claim_confidence": coverage.avg_claim_confidence,
        },
        lineage={
            "analysis_run_id": run.id,
            "startup_id": run.startup_id,
            "action_brief_id": latest_brief.id if latest_brief is not None else None,
            "dossier_id": dossier.id if dossier is not None else None,
            "claim_count": len(claims),
            "recommendation_count": len(recommendations),
            "readiness_check_count": len(readiness_checks),
        },
        alternatives_lost=_alternatives_lost(run, recommendations),
    )


@router.get(
    "/analysis-runs/{analysis_run_id}/evidence-bundle",
    response_model=AnalysisEvidenceBundleRead,
)
def get_analysis_evidence_bundle(
    analysis_run_id: str,
    session: DbSession,
) -> AnalysisEvidenceBundleRead:
    service = ProductService(session)
    run = service.get_analysis_run(analysis_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    return _analysis_evidence_bundle_read(run, session)


@router.patch(
    "/analysis-runs/{analysis_run_id}/claims/{claim_id}/review",
    response_model=ClaimRead,
)
def update_claim_review(
    analysis_run_id: str,
    claim_id: str,
    request: ClaimReviewUpdate,
    session: DbSession,
) -> ClaimRead:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    ledger = ClaimLedgerService(session)
    record = ledger.update_claim_review(
        claim_id,
        review_status=request.review_status,
        reviewer_notes=request.reviewer_notes,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    return _claim_read(record)


@router.get("/activation-playbooks", response_model=ActivationPlaybookListResponse)
def list_activation_playbooks() -> ActivationPlaybookListResponse:
    playbooks = ActivationPlaybookService.get_playbooks()
    items = [
        ActivationPlaybookRead(
            playbook_id=pb.playbook_id,
            name=pb.name,
            description=pb.description,
            target_gap_types=pb.target_gap_types,
            target_claim_types=pb.target_claim_types,
            nvidia_technologies=pb.nvidia_technologies,
            technical_experiment=pb.technical_experiment.model_dump(),
            success_metrics=pb.success_metrics,
            recommended_motion=pb.recommended_motion,
            prerequisites=pb.prerequisites,
            evidence_requirements=pb.evidence_requirements,
            risks=pb.risks,
            expected_value=pb.expected_value,
            implementation_complexity=pb.implementation_complexity,
            version=pb.version,
        )
        for pb in playbooks
    ]
    return ActivationPlaybookListResponse(playbooks=items, total=len(items))


@router.get(
    "/analysis-runs/{analysis_run_id}/activation-recommendations",
    response_model=ActivationRecommendationListResponse,
)
def list_activation_recommendations(
    analysis_run_id: str,
    session: DbSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ActivationRecommendationListResponse:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    act_service = ActivationPlaybookService(session)
    items_raw = act_service.get_recommendations_for_run(analysis_run_id)
    items = [_activation_rec_read(r) for r in items_raw]
    total = len(items)
    page = items[offset : offset + limit]
    return ActivationRecommendationListResponse(items=page, total=total, offset=offset, limit=limit)


@router.post(
    "/analysis-runs/{analysis_run_id}/activation-recommendations/generate",
    response_model=GenerateActivationRecommendationsResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_activation_recommendations(
    analysis_run_id: str,
    _gate: ProductReady,
    session: DbSession,
) -> GenerateActivationRecommendationsResponse:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    act_service = ActivationPlaybookService(session)
    raw = act_service.persist_recommendations_for_run(analysis_run_id)
    items = [_activation_rec_read(r) for r in raw]
    return GenerateActivationRecommendationsResponse(recommendations=items, total=len(items))


def _dossier_read(record: ActivationDossierRecord) -> ActivationDossierRead:
    return ActivationDossierRead(
        id=record.id,
        analysis_run_id=record.analysis_run_id,
        version=record.version,
        schema_version=record.schema_version,
        dossier_json=record.dossier_json,
        dossier_markdown=record.dossier_markdown,
        is_latest=record.is_latest,
        evidence_coverage=record.evidence_coverage,
        unsupported_claim_count=record.unsupported_claim_count,
        top_activation_playbook_id=record.top_activation_playbook_id,
        recommended_motion=record.recommended_motion,
        review_status=record.review_status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post(
    "/analysis-runs/{analysis_run_id}/dossier",
    response_model=ActivationDossierGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dossier(
    analysis_run_id: str,
    _gate: ProductReady,
    session: DbSession,
    force: bool = Query(default=False, description="Force regeneration of a new version"),
) -> ActivationDossierGenerateResponse:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    dossier_svc = ActivationDossierService(session)
    existing = dossier_svc.get_latest_dossier(analysis_run_id)
    is_new = force or existing is None
    if force or existing is None:
        record = dossier_svc.build_dossier_for_analysis_run(analysis_run_id, force_new_version=force)
    else:
        record = existing
    return ActivationDossierGenerateResponse(
        dossier=_dossier_read(record),
        version=record.version,
        is_new=is_new,
    )


@router.get(
    "/analysis-runs/{analysis_run_id}/dossier",
    response_model=ActivationDossierRead,
)
def get_dossier(
    analysis_run_id: str,
    session: DbSession,
) -> ActivationDossierRead:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    dossier_svc = ActivationDossierService(session)
    record = dossier_svc.get_latest_dossier(analysis_run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dossier found for this analysis run. Generate one first with POST.",
        )
    return _dossier_read(record)


@router.get(
    "/analysis-runs/{analysis_run_id}/dossier/markdown",
    response_model=ActivationDossierMarkdownRead,
)
def get_dossier_markdown(
    analysis_run_id: str,
    session: DbSession,
) -> ActivationDossierMarkdownRead:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    dossier_svc = ActivationDossierService(session)
    record = dossier_svc.get_latest_dossier(analysis_run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dossier found for this analysis run. Generate one first with POST.",
        )
    return ActivationDossierMarkdownRead(
        markdown=record.dossier_markdown,
        dossier_id=record.id,
        version=record.version,
    )


@router.post(
    "/analysis-runs/{analysis_run_id}/quality-runs",
    response_model=ProductQualityRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_quality_run(
    analysis_run_id: str,
    _gate: ProductReady,
    session: DbSession,
) -> ProductQualityRunRead:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    quality_service = ProductQualityService(session)
    try:
        quality_run = quality_service.run_quality_evaluation_for_analysis_run(analysis_run_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _quality_run_read(quality_run, session)


@router.get(
    "/analysis-runs/{analysis_run_id}/quality-runs",
    response_model=list[ProductQualityRunRead],
)
def list_quality_runs(
    analysis_run_id: str,
    session: DbSession,
) -> list[ProductQualityRunRead]:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    quality_service = ProductQualityService(session)
    runs = quality_service.repository.list_quality_runs_for_analysis_run(analysis_run_id)
    return [_quality_run_read(r, session) for r in runs]


@router.get(
    "/analysis-runs/{analysis_run_id}/quality-runs/latest",
    response_model=ProductQualityRunRead,
)
def get_latest_quality_run(
    analysis_run_id: str,
    session: DbSession,
) -> ProductQualityRunRead:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    quality_service = ProductQualityService(session)
    quality_run = quality_service.repository.get_latest_quality_run_for_analysis_run(analysis_run_id)
    if quality_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quality run found for this analysis run. Run one first with POST.",
        )
    return _quality_run_read(quality_run, session)


@router.get(
    "/analysis-runs/{analysis_run_id}/quality-summary",
    response_model=ProductQualitySummaryRead,
)
def get_quality_summary(
    analysis_run_id: str,
    session: DbSession,
) -> ProductQualitySummaryRead:
    service = ProductService(session)
    if service.get_analysis_run(analysis_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    quality_service = ProductQualityService(session)
    summary = quality_service.summarize_quality_result(analysis_run_id)
    return ProductQualitySummaryRead(**summary)


# ---------------------------------------------------------------------------
# Product Capability & Configuration Endpoints
# ---------------------------------------------------------------------------


@router.get("/product/capabilities", response_model=list[ProductCapabilityRead])
def list_capabilities() -> list[ProductCapabilityRead]:
    svc = ProductReadinessService()
    return [
        ProductCapabilityRead(
            capability_id=c.capability_id,
            name=c.name,
            description=c.description,
            category=c.category,
            required=c.required,
            status=c.status.value,
            status_reason=c.status_reason,
            required_env_vars=c.required_env_vars,
            optional_env_vars=c.optional_env_vars,
            required_extras=c.required_extras,
            required_services=c.required_services,
            setup_instructions=c.setup_instructions,
            failure_mode=c.failure_mode,
            user_visible=c.user_visible,
            documentation_ref=c.documentation_ref,
        )
        for c in svc.list_capabilities()
    ]


@router.get("/product/configuration", response_model=list[ProductConfigurationItemRead])
def list_configuration() -> list[ProductConfigurationItemRead]:
    svc = ProductReadinessService()
    return [
        ProductConfigurationItemRead(
            key=item["key"],
            description=item["description"],
            required=item["required"],
            secret=item["secret"],
            default=item["default"],
            current_value=item["current_value"],
            is_set=item["is_set"],
        )
        for item in svc.list_required_configuration()
    ]


@router.get("/product/setup-checklist", response_model=ProductSetupChecklistRead)
def get_setup_checklist() -> ProductSetupChecklistRead:
    svc = ProductReadinessService()
    items = svc.get_setup_checklist()
    completed = sum(1 for i in items if i["is_set"])
    pending = len(items) - completed
    return ProductSetupChecklistRead(
        items=[
            ProductSetupChecklistItem(
                key=i["key"],
                description=i["description"],
                is_set=i["is_set"],
                required=i["required"],
            )
            for i in items
        ],
        total=len(items),
        completed=completed,
        pending=pending,
    )


@router.get("/product/readiness", response_model=ProductReadinessRead)
def get_product_readiness() -> ProductReadinessRead:
    svc = ProductReadinessService()
    report = svc.get_product_readiness()
    return ProductReadinessRead(
        ready=report.ready,
        blocking_missing_config=report.blocking_missing_config,
        optional_missing_config=report.optional_missing_config,
        unavailable_capabilities=report.unavailable_capabilities,
        degraded_capabilities=report.degraded_capabilities,
        health_checks=report.health_checks,
        setup_checklist=[
            ProductSetupChecklistItem(
                key=i["key"],
                description=i["description"],
                is_set=i["is_set"],
                required=i["required"],
            )
            for i in report.setup_checklist
        ],
        user_messages=report.user_messages,
    )


def _quality_run_read(
    quality_run: ProductQualityRun,
    session: Session,
) -> ProductQualityRunRead:
    from src.quality.repository import ProductQualityRepository

    repo = ProductQualityRepository(session)
    metrics = repo.get_metrics_for_quality_run(quality_run.id)
    return ProductQualityRunRead(
        id=quality_run.id,
        analysis_run_id=quality_run.analysis_run_id,
        dossier_id=quality_run.dossier_id,
        action_brief_id=quality_run.action_brief_id,
        status=quality_run.status,
        started_at=quality_run.started_at,
        completed_at=quality_run.completed_at,
        evaluator_version=quality_run.evaluator_version,
        metrics=[
            ProductQualityMetricRead(
                id=m.id,
                quality_run_id=m.quality_run_id,
                metric_name=m.metric_name,
                metric_value=m.metric_value,
                threshold=m.threshold,
                passed=m.passed,
                severity=m.severity,
                details=m.details_json,
                created_at=m.created_at,
            )
            for m in metrics
        ],
        metrics_json=quality_run.metrics_json,
        summary_json=quality_run.summary_json,
        degraded_reason=quality_run.degraded_reason,
        created_at=quality_run.created_at,
        updated_at=quality_run.updated_at,
    )


def _activation_rec_read(rec: dict) -> ActivationRecommendationRead:
    return ActivationRecommendationRead(
        id=rec.get("id", ""),
        analysis_run_id=rec.get("analysis_run_id", ""),
        playbook_id=rec.get("playbook_id", ""),
        playbook_name=rec.get("playbook_name", ""),
        matched_gap_types=rec.get("matched_gap_types", []),
        matched_claim_ids=rec.get("matched_claim_ids", []),
        nvidia_technologies=rec.get("nvidia_technologies", []),
        technical_experiment=rec.get("technical_experiment", ""),
        success_metrics=rec.get("success_metrics", []),
        recommended_motion=rec.get("recommended_motion", ""),
        priority=rec.get("priority", 4),
        confidence=rec.get("confidence", "low"),
        reasoning=rec.get("reasoning", ""),
        evidence_refs=rec.get("evidence_refs", []),
        risks=rec.get("risks", []),
        next_step=rec.get("next_step", ""),
        created_at=rec.get("created_at"),
        updated_at=rec.get("updated_at"),
    )


# ---------------------------------------------------------------------------
# Discovery Routes
# ---------------------------------------------------------------------------


@router.get("/discovery/sources", response_model=list[DiscoverySourceRead])
def list_discovery_sources(
    session: DbSession,
) -> list[DiscoverySourceRead]:
    svc = StartupDiscoveryService(session)
    sources = svc.list_sources()
    return [DiscoverySourceRead(**s) for s in sources]


@router.post("/discovery/run-source-scraper", response_model=SourceScraperResponse, status_code=201)
def discover_via_source_scraper(
    body: SourceScraperRequest,
    session: DbSession,
) -> SourceScraperResponse:
    svc = StartupDiscoveryService(session)
    try:
        result = svc.run_source_scraper_discovery(body.source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceScraperResponse(**result)


@router.post("/discovery/manual-seed", response_model=ManualSeedResponse, status_code=201)
def discover_manual_seed(
    body: ManualSeedRequest,
    session: DbSession,
) -> ManualSeedResponse:
    svc = StartupDiscoveryService(session)
    result = svc.run_manual_seed_discovery(
        [e.model_dump() for e in body.entries],
    )
    return ManualSeedResponse(**result)


@router.post("/discovery/url-list", response_model=UrlListResponse, status_code=201)
def discover_url_list(
    body: UrlListRequest,
    session: DbSession,
) -> UrlListResponse:
    svc = StartupDiscoveryService(session)
    result = svc.run_url_list_discovery(body.urls)
    return UrlListResponse(**result)


@router.get("/discovery/runs", response_model=DiscoveryRunListResponse)
def list_discovery_runs(
    session: DbSession,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
) -> DiscoveryRunListResponse:
    svc = StartupDiscoveryService(session)
    runs = svc.repo.list_discovery_runs(offset=offset, limit=limit, status=status)
    items = [
        DiscoveryRunRead(
            id=r.id,
            source_id=r.source_id,
            status=r.status,
            error_message=r.error_message,
            results_count=r.results_count,
            candidates_created=r.candidates_created,
            duplicates_found=r.duplicates_found,
            query_json=r.query_json,
            metadata_json=r.metadata_json,
            started_at=r.started_at,
            completed_at=r.completed_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in runs
    ]
    return DiscoveryRunListResponse(items=items, total=len(items), offset=offset, limit=limit)


@router.get("/discovery/runs/{run_id}", response_model=DiscoveryRunRead)
def get_discovery_run(
    run_id: str,
    session: DbSession,
) -> DiscoveryRunRead:
    svc = StartupDiscoveryService(session)
    run = svc.repo.get_discovery_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Discovery run not found: {run_id}")
    return DiscoveryRunRead(
        id=run.id,
        source_id=run.source_id,
        status=run.status,
        error_message=run.error_message,
        results_count=run.results_count,
        candidates_created=run.candidates_created,
        duplicates_found=run.duplicates_found,
        query_json=run.query_json,
        metadata_json=run.metadata_json,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("/discovery/candidates", response_model=DiscoveryCandidateListResponse)
def list_discovery_candidates(
    session: DbSession,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    source_id: str | None = Query(None),
    sector: str | None = Query(None),
    confidence_min: float | None = Query(None, ge=0.0, le=1.0),
    has_website: bool | None = Query(None),
    ai_native_signal: bool | None = Query(None),
) -> DiscoveryCandidateListResponse:
    svc = StartupDiscoveryService(session)
    candidates = svc.list_candidates(
        offset=offset,
        limit=limit,
        status=status,
        source_id=source_id,
        sector=sector,
        confidence_min=confidence_min,
        has_website=has_website,
        ai_native_signal=ai_native_signal,
    )
    items = [
        DiscoveryCandidateRead(
            id=c.id,
            discovery_run_id=c.discovery_run_id,
            source_id=c.source_id,
            discovered_name=c.discovered_name,
            normalized_name=c.normalized_name,
            website=c.website,
            country=c.country,
            sector=c.sector,
            description=c.description,
            source_url=c.source_url,
            raw_text_excerpt=c.raw_text_excerpt,
            ai_native_signals_json=c.ai_native_signals_json,
            evidence_refs_json=c.evidence_refs_json,
            confidence=c.confidence,
            status=c.status,
            promoted_startup_id=c.promoted_startup_id,
            metadata_json=c.metadata_json,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in candidates
    ]
    return DiscoveryCandidateListResponse(items=items, total=len(items), offset=offset, limit=limit)


@router.get("/discovery/candidates/{candidate_id}", response_model=DiscoveryCandidateRead)
def get_discovery_candidate(
    candidate_id: str,
    session: DbSession,
) -> DiscoveryCandidateRead:
    svc = StartupDiscoveryService(session)
    c = svc.get_candidate_detail(candidate_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Candidate not found: {candidate_id}")
    return DiscoveryCandidateRead(
        id=c.id,
        discovery_run_id=c.discovery_run_id,
        source_id=c.source_id,
        discovered_name=c.discovered_name,
        normalized_name=c.normalized_name,
        website=c.website,
        country=c.country,
        sector=c.sector,
        description=c.description,
        source_url=c.source_url,
        raw_text_excerpt=c.raw_text_excerpt,
        ai_native_signals_json=c.ai_native_signals_json,
        evidence_refs_json=c.evidence_refs_json,
        confidence=c.confidence,
        status=c.status,
        promoted_startup_id=c.promoted_startup_id,
        metadata_json=c.metadata_json,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post(
    "/discovery/candidates/{candidate_id}/promote",
    response_model=PromoteCandidateResponse,
)
def promote_discovery_candidate(
    candidate_id: str,
    session: DbSession,
) -> PromoteCandidateResponse:
    svc = StartupDiscoveryService(session)
    try:
        result = svc.promote_candidate(candidate_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"Candidate not found: {candidate_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PromoteCandidateResponse(**result)


@router.post(
    "/discovery/candidates/{candidate_id}/dedup",
    response_model=DedupCandidateResponse,
)
def dedup_discovery_candidate(
    candidate_id: str,
    session: DbSession,
) -> DedupCandidateResponse:
    svc = StartupDiscoveryService(session)
    result = svc.deduplicate_candidate(candidate_id)
    if result.get("_error") == "not_found":
        raise HTTPException(status_code=404, detail=f"Candidate not found: {candidate_id}")
    return DedupCandidateResponse(
        duplicate_of_candidate_id=result.get("duplicate_of_candidate_id"),
        duplicate_of_startup_id=result.get("duplicate_of_startup_id"),
    )


@router.get("/product/quality-report")
def get_product_quality_report(session: DbSession) -> dict[str, Any]:
    """Aggregate latest product quality evidence for the Product UI.

    This keeps the UI bound to a real backend endpoint instead of a dead/mock
    route. It summarizes the latest persisted quality runs and readiness state.
    """
    readiness = ProductReadinessService().get_product_readiness()
    metrics: dict[str, Any] = {}
    try:
        runs = session.query(ProductQualityRun).order_by(ProductQualityRun.created_at.desc()).limit(20).all()
        for idx, run in enumerate(runs):
            status_value = str(run.overall_status or run.status or "unknown")
            metrics[f"quality_run_{idx}"] = {
                "passed": status_value.upper() in {"PASS", "PASSED", "COMPLETED"},
                "status": status_value,
                "analysis_run_id": run.analysis_run_id,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
    except Exception as exc:
        metrics["quality_report_error"] = {"passed": False, "status": "error", "detail": str(exc)}
    metrics["product_readiness"] = {
        "passed": bool(readiness.ready),
        "status": "pass" if readiness.ready else "fail",
        "capabilities": getattr(readiness, "capabilities", {}),
    }
    status_value = "pass" if all(bool(m.get("passed")) for m in metrics.values() if isinstance(m, dict)) else "fail"
    from src.quality.constants import THRESHOLDS

    return {
        "status": status_value,
        "summary": "Aggregated product quality and readiness report",
        "metrics": metrics,
        "thresholds": {
            metric: {
                "threshold": spec.get("threshold"),
                "operator": spec.get("operator"),
                "severity": spec.get("severity"),
            }
            for metric, spec in THRESHOLDS.items()
        },
        "last_updated": datetime.now(UTC).isoformat(),
    }


@router.get("/radar/dashboard")
def get_radar_dashboard(
    session: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Unified company dashboard backed by runtime artifacts only."""
    from src.services.product.radar_dashboard_service import RadarDashboardService

    return RadarDashboardService(session).dashboard(limit=limit)


@router.post("/radar/dashboard/populate")
def populate_radar_dashboard(
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    source_limit: int = Query(default=6, ge=0, le=20),
    pipeline_limit: int = Query(default=5, ge=0, le=25),
    run_pipeline: bool = Query(default=True),
    force_rerun: bool = Query(default=False),
) -> dict[str, Any]:
    """Run the single central discovery-to-recommendation pipeline for the dashboard.

    No static companies or mock recommendations are injected. If a source cannot
    run because configuration, robots/terms, network, API key, or dependency
    readiness is missing, the response reports the blocker instead of silently
    fabricating data.
    """
    from src.services.product.radar_dashboard_service import PopulateOptions, RadarDashboardService

    options = PopulateOptions(
        limit=limit,
        source_limit=source_limit,
        pipeline_limit=pipeline_limit,
        run_pipeline=run_pipeline,
        force_rerun=force_rerun,
    )
    return RadarDashboardService(session).populate(options)
