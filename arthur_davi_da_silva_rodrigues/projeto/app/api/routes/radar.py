from fastapi import APIRouter

from app.api.schemas import RadarRequest, RadarResponse
from app.classification.maturity import classify_ai_maturity
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.extraction.startup import extract_startup_profile_from_source
from app.radar.scoring import score_threat_opportunity_radar
from app.recommendations.engine import generate_recommendations

router = APIRouter()


@router.post("/threat-opportunity")
def score_radar(request: RadarRequest) -> RadarResponse:
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

    return RadarResponse(
        wrapper_risk=radar.wrapper_risk,
        defensibility=radar.defensibility,
        nvidia_fit=radar.nvidia_fit,
        outreach_urgency=radar.outreach_urgency,
        summary=radar.summary,
        recommended_focus=radar.recommended_focus,
    )
