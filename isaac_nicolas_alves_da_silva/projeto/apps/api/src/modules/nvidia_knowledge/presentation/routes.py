"""Rotas HTTP do modulo NVIDIA Knowledge."""

from fastapi import APIRouter, HTTPException, Query

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaKnowledgeSourcesInput,
    ListNvidiaTechnologiesInput,
    SubmitNvidiaKnowledgeSourcesInput,
)
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
    NvidiaTechnologyCategory,
)
from apps.api.src.modules.nvidia_knowledge.domain.exceptions import (
    NvidiaTechnologyNotFoundError,
)
from apps.api.src.modules.nvidia_knowledge.factories.nvidia_knowledge_factory import (
    NvidiaKnowledgeFactory,
)

from .schemas import (
    NvidiaKnowledgeSourceResponse,
    NvidiaTechnologyResponse,
    SubmitNvidiaKnowledgeSourcesRequest,
    SubmitNvidiaKnowledgeSourcesResponse,
)

router = APIRouter(
    prefix="/nvidia-knowledge",
    tags=["nvidia-knowledge"],
)


@router.get("/technologies", response_model=list[NvidiaTechnologyResponse])
async def list_technologies(
    category: NvidiaTechnologyCategory | None = None,
    query: str | None = Query(default=None, min_length=1),
) -> list[NvidiaTechnologyResponse]:
    """Lista tecnologias NVIDIA do catalogo inicial."""

    catalog = NvidiaKnowledgeFactory.create_catalog()
    views = await catalog.list_technologies(
        ListNvidiaTechnologiesInput(category=category, query=query)
    )
    return [NvidiaTechnologyResponse.from_view(view) for view in views]


@router.get("/technologies/{slug}", response_model=NvidiaTechnologyResponse)
async def get_technology(slug: str) -> NvidiaTechnologyResponse:
    """Retorna uma tecnologia NVIDIA por slug."""

    catalog = NvidiaKnowledgeFactory.create_catalog()
    try:
        view = await catalog.get_technology(slug)
    except NvidiaTechnologyNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return NvidiaTechnologyResponse.from_view(view)


@router.get("/sources", response_model=list[NvidiaKnowledgeSourceResponse])
async def list_sources(
    priority: NvidiaKnowledgeSourcePriority | None = None,
    technology_slug: str | None = Query(default=None, min_length=1),
    query: str | None = Query(default=None, min_length=1),
) -> list[NvidiaKnowledgeSourceResponse]:
    """Lista fontes planejadas para ingestao NVIDIA Knowledge V2."""

    registry = NvidiaKnowledgeFactory.create_source_registry()
    views = await registry.list_sources(
        ListNvidiaKnowledgeSourcesInput(
            priority=priority,
            technology_slug=technology_slug,
            query=query,
        )
    )
    return [NvidiaKnowledgeSourceResponse.from_view(view) for view in views]


@router.post(
    "/ingestion/jobs",
    response_model=SubmitNvidiaKnowledgeSourcesResponse,
)
async def submit_sources_for_ingestion(
    request: SubmitNvidiaKnowledgeSourcesRequest | None = None,
) -> SubmitNvidiaKnowledgeSourcesResponse:
    """Submete fontes NVIDIA Knowledge para orquestracao de ingestao."""

    request = request or SubmitNvidiaKnowledgeSourcesRequest()
    submitter = NvidiaKnowledgeFactory.create_submit_sources_for_ingestion()
    view = await submitter.execute(
        SubmitNvidiaKnowledgeSourcesInput(
            priority=request.priority,
            technology_slug=request.technology_slug,
            query=request.query,
            limit=request.limit,
        )
    )
    return SubmitNvidiaKnowledgeSourcesResponse.from_view(view)
