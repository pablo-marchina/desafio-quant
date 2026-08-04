from __future__ import annotations

from typing import TypedDict

from radar.schemas import (
    EvidenceClaim,
    EvidenceValidationReport,
    ExecutiveBriefing,
    NvidiaKnowledgeChunk,
    NvidiaRecommendation,
    PipelineError,
    SearchPlan,
    SourceDocument,
    StartupClassification,
    StartupProfile,
    TechnicalGap,
)


class RadarState(TypedDict, total=False):
    query: str
    startup_name: str
    search_plan: SearchPlan
    sources: list[SourceDocument]
    extracted_startups: list[StartupProfile]
    claims: list[EvidenceClaim]
    validation: EvidenceValidationReport
    classification: StartupClassification
    technical_gaps: list[TechnicalGap]
    nvidia_context: list[NvidiaKnowledgeChunk]
    recommendations: list[NvidiaRecommendation]
    briefing: ExecutiveBriefing
    errors: list[PipelineError]
    review_required: bool
    collection_attempts: int
