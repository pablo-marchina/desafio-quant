from unicodedata import normalize
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.schemas import (
    BriefingGenerationRequest,
    BriefingGenerationResponse,
    BriefingReadResponse,
    EmailReportRequest,
    EmailReportResponse,
    PersistedBriefingResponse,
)
from app.briefings.emailer import EmailNotConfiguredError, send_markdown_report_email
from app.briefings.generator import generate_executive_briefing
from app.classification.maturity import classify_ai_maturity
from app.db.session import get_db_session
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.extraction.startup import extract_startup_profile_from_source
from app.persistence.analysis import get_briefing, persist_briefing
from app.radar.scoring import score_threat_opportunity_radar
from app.recommendations.engine import generate_recommendations
from app.settings import get_settings

router = APIRouter()
DB_SESSION_DEPENDENCY = Depends(get_db_session)


@router.post("")
def generate_briefing(
    request: BriefingGenerationRequest,
    db_session: Session = DB_SESSION_DEPENDENCY,
) -> BriefingGenerationResponse:
    startup_profile = extract_startup_profile_from_source(
        url=request.url,
        title=request.title,
        extracted_text=request.extracted_text,
    )
    assessment = classify_ai_maturity(startup_profile, request.extracted_text)
    gap_report = diagnose_ai_stack_gaps(startup_profile, assessment, request.extracted_text)
    recommendation_report = generate_recommendations(gap_report.gaps)
    radar = score_threat_opportunity_radar(
        startup_profile=startup_profile,
        assessment=assessment,
        gap_report=gap_report,
        recommendation_report=recommendation_report,
    )
    markdown = generate_executive_briefing(
        startup_profile=startup_profile,
        assessment=assessment,
        gap_report=gap_report,
        recommendation_report=recommendation_report,
        radar=radar,
    )
    briefing_title = (
        f"{startup_profile.name or 'Startup desconhecida'} - Relatório NVIDIA Startup AI Radar"
    )
    persisted = None

    if request.persist and request.startup_id:
        briefing_id = persist_briefing(
            db_session=db_session,
            startup_id=request.startup_id,
            title=briefing_title,
            markdown=markdown,
            source_urls=(startup_profile.website,),
        )
        persisted = PersistedBriefingResponse(briefing_id=briefing_id)

    return BriefingGenerationResponse(
        title=briefing_title,
        markdown=markdown,
        source_urls=(startup_profile.website,),
        persisted=persisted,
    )


@router.get("/{briefing_id}")
def read_briefing(
    briefing_id: UUID,
    db_session: Session = DB_SESSION_DEPENDENCY,
) -> BriefingReadResponse:
    briefing = _load_briefing_or_503(db_session, briefing_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    return BriefingReadResponse(
        id=str(briefing.id),
        startup_id=str(briefing.startup_id),
        title=briefing.title,
        markdown=briefing.markdown,
        source_urls=tuple(briefing.source_summary.get("source_urls", [])),
    )


@router.post("/{briefing_id}/export")
def export_briefing(
    briefing_id: UUID,
    db_session: Session = DB_SESSION_DEPENDENCY,
) -> Response:
    briefing = _load_briefing_or_503(db_session, briefing_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    filename = _markdown_filename(briefing.title)
    return Response(
        content=briefing.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/email")
def email_report(request: EmailReportRequest) -> EmailReportResponse:
    settings = get_settings()
    try:
        result = send_markdown_report_email(
            settings=settings,
            to_email=request.to_email,
            subject=request.subject,
            markdown=request.markdown,
        )
    except EmailNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EmailReportResponse(status=result.status, detail=result.detail)


def _markdown_filename(title: str) -> str:
    ascii_title = normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = "".join(character.lower() if character.isalnum() else "-" for character in ascii_title)
    slug = "-".join(part for part in slug.split("-") if part)
    return f"{slug or 'relatorio'}.md"


def _load_briefing_or_503(db_session: Session, briefing_id: UUID) -> object | None:
    try:
        return get_briefing(db_session, briefing_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Armazenamento de relatório indisponível",
        ) from exc
