"""Rotas HTTP do modulo RAG."""

from fastapi import APIRouter, HTTPException, status

from apps.api.src.modules.rag.application.dto import (
    AnswerQuestionInput,
    SearchEvidenceInput,
)
from apps.api.src.modules.rag.domain.exceptions import (
    EmptyRagQueryError,
    RagAnswerGenerationError,
    RagAnswerServiceUnavailableError,
    RagEvidenceNotFoundError,
    RagSearchServiceUnavailableError,
)
from apps.api.src.modules.rag.factories.rag_factory import RagFactory

from .schemas import (
    AnswerQuestionRequest,
    RagAnswerResponse,
    SearchEvidenceRequest,
    SearchEvidenceResponse,
)

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


@router.post("/search", response_model=SearchEvidenceResponse)
async def search_evidence(body: SearchEvidenceRequest) -> SearchEvidenceResponse:
    """Busca evidencias semanticamente relevantes."""

    use_case = RagFactory.create_search_evidence()
    try:
        view = await use_case.execute(
            SearchEvidenceInput(
                query=body.query,
                limit=body.limit,
                source_type=body.source_type,
                document_ids=body.document_ids,
            )
        )
    except EmptyRagQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RagSearchServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return SearchEvidenceResponse.from_view(view)


@router.post("/answer", response_model=RagAnswerResponse)
async def answer_question(body: AnswerQuestionRequest) -> RagAnswerResponse:
    """Responde uma pergunta usando evidencias recuperadas e citacoes."""

    use_case = RagFactory.create_answer_question()
    try:
        view = await use_case.execute(
            AnswerQuestionInput(
                query=body.query,
                limit=body.limit,
                source_type=body.source_type,
                document_ids=body.document_ids,
            )
        )
    except EmptyRagQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RagEvidenceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (
        RagSearchServiceUnavailableError,
        RagAnswerServiceUnavailableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except RagAnswerGenerationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    return RagAnswerResponse.from_view(view)
