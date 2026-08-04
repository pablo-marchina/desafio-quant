from dataclasses import dataclass


@dataclass(frozen=True)
class TechnologyRecommendation:
    gap_type: str
    technology_name: str
    source_url: str
    priority: str
    complexity: str
    technical_rationale: str
    business_rationale: str
    next_action: str


@dataclass(frozen=True)
class RecommendationReport:
    recommendations: tuple[TechnologyRecommendation, ...]
    summary: str
