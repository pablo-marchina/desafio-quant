"""Estado compartilhado do Recommendation Graph."""

from typing import TypedDict

from apps.api.src.modules.agents.application.dto import (
    RecommendationAgentInput,
    RecommendationAgentResult,
    RecommendationCandidate,
)


class RecommendationState(TypedDict, total=False):
    """Estado minimo usado na V11 do Recommendation Agent."""

    recommendation_input: RecommendationAgentInput
    prepared_context: str
    candidates: list[RecommendationCandidate]
    reviewed_candidates: list[RecommendationCandidate]
    result: RecommendationAgentResult
