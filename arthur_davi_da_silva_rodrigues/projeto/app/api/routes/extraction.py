from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import (
    EvidenceClaimResponse,
    PersistedStartupAnalysisResponse,
    StartupProfileDraftResponse,
    StartupProfileExtractionRequest,
)
from app.collectors.source_types import classify_source_type
from app.db.session import get_db_session
from app.extraction.schemas import EvidenceClaimDraft
from app.extraction.startup import extract_startup_profile_from_source
from app.persistence.analysis import persist_startup_analysis

router = APIRouter()
DB_SESSION_DEPENDENCY = Depends(get_db_session)


@router.post("/startup-profile")
def extract_startup_profile(
    request: StartupProfileExtractionRequest,
    db_session: Session = DB_SESSION_DEPENDENCY,
) -> StartupProfileDraftResponse:
    startup_profile = extract_startup_profile_from_source(
        url=request.url,
        title=request.title,
        extracted_text=request.extracted_text,
    )
    persisted = None

    if request.persist:
        persisted_analysis = persist_startup_analysis(
            db_session=db_session,
            startup_profile=startup_profile,
            source_type=classify_source_type(request.url),
            title=request.title,
            extracted_text=request.extracted_text,
        )
        persisted = PersistedStartupAnalysisResponse(
            startup_id=persisted_analysis.startup_id,
            source_document_id=persisted_analysis.source_document_id,
            evidence_claim_ids=persisted_analysis.evidence_claim_ids,
            technology_signal_ids=persisted_analysis.technology_signal_ids,
        )

    return StartupProfileDraftResponse(
        name=startup_profile.name,
        website=startup_profile.website,
        description=startup_profile.description,
        ai_usage_summary=startup_profile.ai_usage_summary,
        sectors=startup_profile.sectors,
        technology_signals=startup_profile.technology_signals,
        evidence_claims=_claim_responses(startup_profile.evidence_claims),
        accepted_claims=_claim_responses(startup_profile.accepted_claims),
        review_claims=_claim_responses(startup_profile.review_claims),
        persisted=persisted,
    )


def _claim_responses(claims: tuple[EvidenceClaimDraft, ...]) -> tuple[EvidenceClaimResponse, ...]:
    return tuple(
        EvidenceClaimResponse(
            claim=claim.claim,
            claim_type=claim.claim_type,
            supporting_text=claim.supporting_text,
            confidence=claim.confidence,
            validation_status=claim.validation_status,
        )
        for claim in claims
    )
