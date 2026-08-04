"""Rotas HTTP do modulo embeddings."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from apps.api.src.modules.embeddings.domain.exceptions import EmbeddingJobNotFoundError
from apps.api.src.modules.embeddings.factories.embeddings_factory import (
    EmbeddingsFactory,
)

from .schemas import CreateEmbeddingJobRequest, EmbeddingJobResponse

router = APIRouter(
    prefix="/embeddings",
    tags=["embeddings"],
)


@router.post(
    "/jobs",
    response_model=EmbeddingJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_embedding_job(
    body: CreateEmbeddingJobRequest,
) -> EmbeddingJobResponse:
    """Cria e enfileira um job de embeddings para um documento."""

    from apps.api.src.modules.embeddings.application.dto import (
        CreateEmbeddingJobInput,
    )

    use_case = EmbeddingsFactory.create_create_embedding_job()
    view = await use_case.execute(
        CreateEmbeddingJobInput(document_id=body.document_id)
    )
    return EmbeddingJobResponse.from_view(view)


@router.get(
    "/jobs/{job_id}",
    response_model=EmbeddingJobResponse,
)
async def get_embedding_job(job_id: UUID) -> EmbeddingJobResponse:
    """Retorna o estado atual de um job de embeddings."""

    use_case = EmbeddingsFactory.create_get_embedding_job()
    try:
        view = await use_case.execute(job_id=job_id)
    except EmbeddingJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return EmbeddingJobResponse.from_view(view)
