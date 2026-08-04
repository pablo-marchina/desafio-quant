from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import (
    AiMaturityAssessmentResponse,
    AiMaturityClassificationRequest,
    PersistedAssessmentResponse,
)
from app.classification.maturity import classify_ai_maturity
from app.db.session import get_db_session
from app.extraction.startup import extract_startup_profile_from_source
from app.persistence.analysis import persist_ai_maturity_assessment

router = APIRouter()
DB_SESSION_DEPENDENCY = Depends(get_db_session)


@router.post("/ai-maturity")
def classify_startup_ai_maturity(
    request: AiMaturityClassificationRequest,
    db_session: Session = DB_SESSION_DEPENDENCY,
) -> AiMaturityAssessmentResponse:
    startup_profile = extract_startup_profile_from_source(
        url=request.url,
        title=request.title,
        extracted_text=request.extracted_text,
    )
    assessment = classify_ai_maturity(startup_profile, request.extracted_text)
    persisted = None

    if request.persist and request.startup_id:
        assessment_id = persist_ai_maturity_assessment(
            db_session=db_session,
            startup_id=request.startup_id,
            assessment=assessment,
        )
        persisted = PersistedAssessmentResponse(assessment_id=assessment_id)

    return AiMaturityAssessmentResponse(
        label=assessment.label,
        confidence=assessment.confidence,
        explanation=assessment.explanation,
        scores=assessment.scores,
        persisted=persisted,
    )
