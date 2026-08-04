from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.product_schemas import (
    ProductWorkflowNodeRunRead,
    ProductWorkflowRunCreate,
    ProductWorkflowRunListResponse,
    ProductWorkflowRunRead,
    WorkflowReviewDecisionCreate,
    WorkflowReviewDecisionRead,
    WorkflowReviewPayloadRead,
)
from src.database.models import WorkflowNodeRun, WorkflowRun
from src.database.session import get_db_session
from src.orchestration.runner import _has_langgraph
from src.orchestration.service import WorkflowOrchestrationService
from src.repositories.workflow import WorkflowRepository
from src.services.product.readiness_gate import ReadinessGate

router = APIRouter(tags=["workflows"])
DbSession = Annotated[Session, Depends(get_db_session)]
ProductReady = Annotated[None, Depends(ReadinessGate())]


@router.post(
    "/workflows/product-runs",
    response_model=ProductWorkflowRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_product_workflow_run(
    body: ProductWorkflowRunCreate,
    _gate: ProductReady,
    session: DbSession,
) -> ProductWorkflowRunRead:
    """Persist a durable workflow and return immediately for polling."""
    if body.use_rag is False:
        raise HTTPException(status_code=400, detail="Product pipeline requires RAG; use_rag=false is not allowed.")
    svc = WorkflowOrchestrationService(session)
    try:
        run = svc.enqueue_workflow(
            startup_id=body.startup_id,
            discovery_candidate_id=body.discovery_candidate_id,
            analysis_run_id=body.analysis_run_id,
            use_rag=body.use_rag,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _workflow_run_read(run, [])


@router.get(
    "/workflows/product-runs",
    response_model=ProductWorkflowRunListResponse,
)
def list_product_workflow_runs(
    session: DbSession,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    startup_id: str | None = Query(None),
) -> ProductWorkflowRunListResponse:
    svc = WorkflowOrchestrationService(session)
    items = svc.list_workflows(offset=offset, limit=limit, status=status, startup_id=startup_id)
    return ProductWorkflowRunListResponse(items=items, total=len(items), offset=offset, limit=limit)


@router.get(
    "/workflows/product-runs/{workflow_id}",
    response_model=ProductWorkflowRunRead,
)
def get_product_workflow_run(
    workflow_id: str,
    session: DbSession,
) -> ProductWorkflowRunRead:
    repo = WorkflowRepository(session)
    run = repo.get_workflow_run(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Workflow run not found: {workflow_id}")
    node_runs = repo.list_node_runs(workflow_id)
    return _workflow_run_read(run, node_runs)


@router.get(
    "/workflows/product-runs/{workflow_id}/nodes",
    response_model=list[ProductWorkflowNodeRunRead],
)
def list_workflow_node_runs(
    workflow_id: str,
    session: DbSession,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[ProductWorkflowNodeRunRead]:
    repo = WorkflowRepository(session)
    run = repo.get_workflow_run(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Workflow run not found: {workflow_id}")
    node_runs = repo.list_node_runs(workflow_id, offset=offset, limit=limit)
    return [
        ProductWorkflowNodeRunRead(
            id=nr.id,
            workflow_run_id=nr.workflow_run_id,
            node_name=nr.node_name,
            status=nr.status,
            started_at=nr.started_at,
            completed_at=nr.completed_at,
            error_message=nr.error_message,
            retry_count=nr.retry_count,
            created_at=nr.created_at,
        )
        for nr in node_runs
    ]


@router.get(
    "/workflows/product-runs/{workflow_id}/node-snapshots",
    response_model=list[dict[str, Any]],
)
def list_workflow_node_snapshots(
    workflow_id: str,
    session: DbSession,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Expose persisted node snapshots for audit and failed-run reconstruction."""
    repo = WorkflowRepository(session)
    run = repo.get_workflow_run(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Workflow run not found: {workflow_id}")
    node_runs = repo.list_node_runs(workflow_id, offset=offset, limit=limit)
    return [
        {
            "id": nr.id,
            "workflow_run_id": nr.workflow_run_id,
            "node_name": nr.node_name,
            "status": nr.status,
            "started_at": nr.started_at,
            "completed_at": nr.completed_at,
            "error_message": nr.error_message,
            "retry_count": nr.retry_count,
            "input_snapshot": nr.input_snapshot_json or {},
            "output_snapshot": nr.output_snapshot_json or {},
            "metadata": nr.metadata_json or {},
            "created_at": nr.created_at,
        }
        for nr in node_runs
    ]


@router.get(
    "/analysis-runs/{analysis_run_id}/workflow",
    response_model=ProductWorkflowRunRead | None,
)
def get_workflow_for_analysis_run(
    analysis_run_id: str,
    session: DbSession,
) -> ProductWorkflowRunRead | None:
    repo = WorkflowRepository(session)
    run = repo.get_workflow_for_analysis_run(analysis_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow found for analysis run: {analysis_run_id}")
    node_runs = repo.list_node_runs(run.id)
    return _workflow_run_read(run, node_runs)


@router.get("/workflows/langgraph-status")
def get_langgraph_status() -> dict[str, bool]:
    return {"langgraph_available": _has_langgraph()}


@router.get(
    "/workflows/{workflow_id}/review-payload",
    response_model=WorkflowReviewPayloadRead,
)
def get_workflow_review_payload(
    workflow_id: str,
    session: DbSession,
) -> WorkflowReviewPayloadRead:
    svc = WorkflowOrchestrationService(session)
    payload = svc.get_review_payload(workflow_id)
    if payload is None:
        run = svc.repo.get_workflow_run(workflow_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Workflow run not found: {workflow_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} has no review payload — it may not have reached needs_review",
        )
    return WorkflowReviewPayloadRead(**payload)


@router.post(
    "/workflows/{workflow_id}/review",
    response_model=WorkflowReviewDecisionRead,
    status_code=201,
)
def submit_workflow_review(
    workflow_id: str,
    body: WorkflowReviewDecisionCreate,
    session: DbSession,
) -> WorkflowReviewDecisionRead:
    svc = WorkflowOrchestrationService(session)
    try:
        result = svc.submit_review(
            workflow_id,
            decision=body.decision,
            reviewer=body.reviewer,
            notes=body.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WorkflowReviewDecisionRead(**result)


@router.post(
    "/workflows/{workflow_id}/resume",
    response_model=ProductWorkflowRunRead,
    status_code=status.HTTP_200_OK,
)
def resume_workflow(
    workflow_id: str,
    body: WorkflowReviewDecisionCreate,
    session: DbSession,
) -> ProductWorkflowRunRead:
    """Resume a workflow that is awaiting human review."""
    repo = WorkflowRepository(session)
    run = repo.get_workflow_run(workflow_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run not found: {workflow_id}",
        )

    status_before = run.status
    thread_id: str | None = None
    review_payload: dict | None = None
    if run.state_json:
        meta = run.state_json.get("metadata_json") or {}
        thread_id = meta.get("_langgraph_thread_id")
        review_payload = run.state_json.get("review_payload")

    review_record_id: str | None = None
    if run.analysis_run_id:
        from src.repositories.review import ReviewDecisionRepository

        review_repo = ReviewDecisionRepository(session)
        try:
            review_record = review_repo.create(
                analysis_run_id=run.analysis_run_id,
                startup_id=run.startup_id or "",
                decision=body.decision,
                reviewer=body.reviewer,
                notes=body.notes,
                thread_id=thread_id,
                review_payload_snapshot=review_payload,
                status_before_resume=status_before,
            )
            session.flush()
            review_record_id = review_record.id
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist review decision.",
            ) from exc

    try:
        svc = WorkflowOrchestrationService(session)
        svc.submit_review(
            workflow_id,
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

    run_after = repo.get_workflow_run(workflow_id)
    if review_record_id is not None and run_after is not None:
        from src.repositories.review import ReviewDecisionRepository

        review_repo = ReviewDecisionRepository(session)
        review_repo.update_status_after_resume(
            review_record_id,
            status_after_resume=run_after.status,
        )

    session.commit()

    if run_after is None:
        run_after = run
    node_runs = repo.list_node_runs(workflow_id)
    return _workflow_run_read(run_after, node_runs)


def _workflow_run_read(
    run: WorkflowRun,
    node_runs: list[WorkflowNodeRun],
) -> ProductWorkflowRunRead:
    return ProductWorkflowRunRead(
        id=run.id,
        startup_id=run.startup_id,
        discovery_candidate_id=run.discovery_candidate_id,
        analysis_run_id=run.analysis_run_id,
        status=run.status,
        current_node=run.current_node,
        graph_version=run.graph_version,
        error_message=run.error_message,
        degraded_reason=run.degraded_reason,
        state=run.state_json or {},
        nodes=[
            ProductWorkflowNodeRunRead(
                id=nr.id,
                workflow_run_id=nr.workflow_run_id,
                node_name=nr.node_name,
                status=nr.status,
                started_at=nr.started_at,
                completed_at=nr.completed_at,
                error_message=nr.error_message,
                retry_count=nr.retry_count,
                created_at=nr.created_at,
            )
            for nr in node_runs
        ],
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
