from fastapi import APIRouter

from app.api.schemas import GapDiagnosisReportResponse, GapDiagnosisRequest, GapDiagnosisResponse
from app.classification.maturity import classify_ai_maturity
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.extraction.startup import extract_startup_profile_from_source

router = APIRouter()


@router.post("/gaps")
def diagnose_gaps(request: GapDiagnosisRequest) -> GapDiagnosisReportResponse:
    startup_profile = extract_startup_profile_from_source(
        url=request.url,
        title=request.title,
        extracted_text=request.extracted_text,
    )
    assessment = classify_ai_maturity(startup_profile, request.extracted_text)
    report = diagnose_ai_stack_gaps(startup_profile, assessment, request.extracted_text)

    return GapDiagnosisReportResponse(
        summary=report.summary,
        gaps=tuple(
            GapDiagnosisResponse(
                gap_type=gap.gap_type,
                priority=gap.priority,
                confidence=gap.confidence,
                evidence_basis=gap.evidence_basis,
                rationale=gap.rationale,
                suggested_action=gap.suggested_action,
            )
            for gap in report.gaps
        ),
    )
