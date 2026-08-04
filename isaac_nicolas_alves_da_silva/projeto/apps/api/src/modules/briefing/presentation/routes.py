"""Rotas HTTP do modulo briefing."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from apps.api.src.modules.briefing.application.dto import (
    GenerateBriefingInput,
    ReviewBriefingInput,
)
from apps.api.src.modules.briefing.domain.exceptions import (
    BriefingError,
    BriefingNotFoundError,
    BriefingRenderingError,
    StartupProfileUnavailableError,
)
from apps.api.src.modules.briefing.factories.briefing_factory import BriefingFactory

from .schemas import BriefingResponse, GenerateBriefingRequest, ReviewBriefingRequest

router = APIRouter(
    prefix="/briefings",
    tags=["briefing"],
)


@router.post(
    "",
    response_model=BriefingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_briefing(body: GenerateBriefingRequest) -> BriefingResponse:
    """Gera e persiste o briefing executivo mais recente de uma startup."""

    use_case = BriefingFactory.create_generate_briefing()
    try:
        view = await use_case.execute(
            GenerateBriefingInput(startup_id=body.startup_id)
        )
    except StartupProfileUnavailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return BriefingResponse.from_view(view)


@router.get("/{briefing_id}", response_model=BriefingResponse)
async def get_briefing(briefing_id: UUID) -> BriefingResponse:
    """Retorna um briefing por id."""

    use_case = BriefingFactory.create_get_briefing()
    try:
        view = await use_case.execute(briefing_id=briefing_id)
    except BriefingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return BriefingResponse.from_view(view)


@router.get("/{briefing_id}/export")
async def export_briefing_pdf(briefing_id: UUID) -> Response:
    """Exporta o briefing como PDF, preservando citacoes como links."""

    use_case = BriefingFactory.create_export_briefing_pdf()
    try:
        pdf = await use_case.execute(briefing_id=briefing_id)
    except BriefingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BriefingRenderingError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return Response(
        content=pdf.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf.filename}"'},
    )


@router.patch("/{briefing_id}/review", response_model=BriefingResponse)
async def review_briefing(
    briefing_id: UUID,
    body: ReviewBriefingRequest,
) -> BriefingResponse:
    """Registra aprovacao/rejeicao humana simples de um briefing."""

    use_case = BriefingFactory.create_review_briefing()
    try:
        view = await use_case.execute(
            ReviewBriefingInput(
                briefing_id=briefing_id,
                status=body.status,
                comment=body.comment,
                reviewed_by=body.reviewed_by,
            )
        )
    except BriefingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BriefingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BriefingResponse.from_view(view)


@router.get("", response_model=list[BriefingResponse])
async def list_briefings(startup_id: UUID) -> list[BriefingResponse]:
    """Lista briefings de uma startup."""

    use_case = BriefingFactory.create_list_briefings()
    views = await use_case.execute(startup_id=startup_id)
    return [BriefingResponse.from_view(view) for view in views]
