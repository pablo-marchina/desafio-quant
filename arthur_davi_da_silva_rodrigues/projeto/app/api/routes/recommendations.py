from fastapi import APIRouter

from app.api.schemas import (
    RecommendationReportResponse,
    RecommendationRequest,
    TechnologyRecommendationResponse,
)
from app.classification.maturity import classify_ai_maturity
from app.diagnostics.gaps import diagnose_ai_stack_gaps
from app.extraction.startup import extract_startup_profile_from_source
from app.recommendations.engine import generate_recommendations

router = APIRouter()


@router.post("")
def recommend_nvidia_technologies(
    request: RecommendationRequest,
) -> RecommendationReportResponse:
    startup_profile = extract_startup_profile_from_source(
        url=request.url,
        title=request.title,
        extracted_text=request.extracted_text,
    )
    assessment = classify_ai_maturity(startup_profile, request.extracted_text)
    gap_report = diagnose_ai_stack_gaps(startup_profile, assessment, request.extracted_text)
    recommendation_report = generate_recommendations(gap_report.gaps)

    return RecommendationReportResponse(
        summary=recommendation_report.summary,
        recommendations=tuple(
            TechnologyRecommendationResponse(
                gap_type=recommendation.gap_type,
                technology_name=recommendation.technology_name,
                source_url=recommendation.source_url,
                priority=recommendation.priority,
                complexity=recommendation.complexity,
                technical_rationale=recommendation.technical_rationale,
                business_rationale=recommendation.business_rationale,
                next_action=recommendation.next_action,
            )
            for recommendation in recommendation_report.recommendations
        ),
    )
