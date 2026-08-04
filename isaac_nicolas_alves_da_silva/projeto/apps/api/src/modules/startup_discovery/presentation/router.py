"""Rotas HTTP do modulo startup_discovery."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from apps.api.src.modules.startup_discovery.application.dto import (
    CandidateView,
    DiscoveryRunView,
)
from apps.api.src.modules.startup_discovery.domain.exceptions import (
    DiscoveryRunNotFoundError,
)
from apps.api.src.modules.startup_discovery.factories.startup_discovery_factory import (
    StartupDiscoveryFactory,
)
from apps.api.src.modules.startup_discovery.presentation.schemas import (
    CandidateListResponse,
    CandidateResponse,
    DiscoveryRunResponse,
    SubmittedUrlResponse,
)

router = APIRouter(prefix="/startup-discovery", tags=["startup-discovery"])


def _to_response(view: DiscoveryRunView) -> DiscoveryRunResponse:
    return DiscoveryRunResponse(
        id=view.id,
        status=view.status,
        hubs_processed=view.hubs_processed,
        urls_found=view.urls_found,
        jobs_submitted=view.jobs_submitted,
        candidates_discovered=view.candidates_discovered,
        candidates_enriched=view.candidates_enriched,
        error_message=view.error_message,
        created_at=view.created_at,
        completed_at=view.completed_at,
        submitted_urls=[
            SubmittedUrlResponse(
                hub_name=u.hub_name,
                url=u.url,
                job_id=u.job_id,
                name=u.name,
                hub_profile_url=u.hub_profile_url,
                short_description=u.short_description,
                declared_sector=u.declared_sector,
            )
            for u in view.submitted_urls
        ],
    )


def _candidate_to_response(view: CandidateView) -> CandidateResponse:
    return CandidateResponse(
        id=view.id,
        run_id=view.run_id,
        name=view.name,
        normalized_name=view.normalized_name,
        discovery_source=view.discovery_source,
        category=view.category,
        rank=view.rank,
        description=view.description,
        official_website_url=view.official_website_url,
        official_site_confidence=view.official_site_confidence,
        enrichment_sources=view.enrichment_sources,
        status=view.status,
        rejection_reason=view.rejection_reason,
        url_ingestion_job_id=view.url_ingestion_job_id,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


@router.post(
    "/runs",
    response_model=DiscoveryRunResponse,
    status_code=201,
    summary="Dispara uma rodada de descoberta de startups nos hubs cadastrados.",
)
async def run_discovery() -> DiscoveryRunResponse:
    use_case = StartupDiscoveryFactory.create_run_discovery()
    view = await use_case.execute()
    return _to_response(view)


@router.get(
    "/runs/{run_id}",
    response_model=DiscoveryRunResponse,
    summary="Retorna o resultado de uma rodada de descoberta pelo id.",
)
async def get_discovery_run(run_id: UUID) -> DiscoveryRunResponse:
    use_case = StartupDiscoveryFactory.create_get_discovery_run()
    try:
        view = await use_case.execute(run_id)
    except DiscoveryRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(view)


@router.get(
    "/runs/{run_id}/candidates",
    response_model=CandidateListResponse,
    summary="Lista os candidatos descobertos por nome em um run especifico.",
)
async def list_candidates(run_id: UUID) -> CandidateListResponse:
    from apps.api.src.modules.startup_discovery.infrastructure.database.postgres_unit_of_work import (
        PostgresDiscoveryUnitOfWork,
    )
    from apps.api.src.modules.startup_discovery.application.use_cases.run_discovery import (
        _to_candidate_view,
    )

    async with PostgresDiscoveryUnitOfWork() as uow:
        run = await uow.repository.get_by_id(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"DiscoveryRun {run_id} nao encontrado.")
        candidates = await uow.candidate_repository.list_by_run_id(run_id)

    views = [_to_candidate_view(c) for c in candidates]
    return CandidateListResponse(
        run_id=run_id,
        total=len(views),
        candidates=[_candidate_to_response(v) for v in views],
    )
