"""Rotas HTTP do modulo recommendations."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from apps.api.src.modules.recommendations.application.dto import (
    GenerateRecommendationsInput,
    ReviewRecommendationInput,
)
from apps.api.src.modules.recommendations.domain.exceptions import (
    RecommendationError,
    RecommendationNotFoundError,
    StartupProfileUnavailableError,
)
from apps.api.src.modules.recommendations.factories.recommendations_factory import (
    RecommendationsFactory,
)

from .schemas import (
    GenerateRecommendationsRequest,
    RecommendationResponse,
    ReviewRecommendationRequest,
    TechnologyStatsResponse,
)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
)


@router.post(
    "",
    response_model=list[RecommendationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_recommendations(
    body: GenerateRecommendationsRequest,
) -> list[RecommendationResponse]:
    """Gera e persiste recomendacoes NVIDIA para uma startup."""

    use_case = RecommendationsFactory.create_generate_recommendations()
    try:
        views = await use_case.execute(
            GenerateRecommendationsInput(startup_id=body.startup_id)
        )
    except StartupProfileUnavailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return [RecommendationResponse.from_view(view) for view in views]


@router.get("/stats", response_model=TechnologyStatsResponse)
async def get_technology_stats(
    limit: int = 10,
) -> TechnologyStatsResponse:
    """Retorna as tecnologias NVIDIA mais recomendadas no portfolio (para graficos)."""

    use_case = RecommendationsFactory.create_get_technology_stats()
    view = await use_case.execute(limit=max(1, min(limit, 20)))
    return TechnologyStatsResponse.from_view(view)


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(recommendation_id: UUID) -> RecommendationResponse:
    """Retorna uma recomendacao por id."""

    use_case = RecommendationsFactory.create_get_recommendation()
    try:
        view = await use_case.execute(recommendation_id=recommendation_id)
    except RecommendationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return RecommendationResponse.from_view(view)


@router.patch("/{recommendation_id}/review", response_model=RecommendationResponse)
async def review_recommendation(
    recommendation_id: UUID,
    body: ReviewRecommendationRequest,
) -> RecommendationResponse:
    """Registra aprovacao/rejeicao humana simples de uma recomendacao."""

    use_case = RecommendationsFactory.create_review_recommendation()
    try:
        view = await use_case.execute(
            ReviewRecommendationInput(
                recommendation_id=recommendation_id,
                status=body.status,
                comment=body.comment,
                reviewed_by=body.reviewed_by,
            )
        )
    except RecommendationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RecommendationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return RecommendationResponse.from_view(view)


@router.get("", response_model=list[RecommendationResponse])
async def list_recommendations(startup_id: UUID) -> list[RecommendationResponse]:
    """Lista recomendacoes de uma startup."""

    use_case = RecommendationsFactory.create_list_recommendations()
    views = await use_case.execute(startup_id=startup_id)
    return [RecommendationResponse.from_view(view) for view in views]
