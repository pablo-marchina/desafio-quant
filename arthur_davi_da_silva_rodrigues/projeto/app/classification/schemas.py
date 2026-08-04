from dataclasses import dataclass


@dataclass(frozen=True)
class AiMaturityAssessmentDraft:
    label: str
    confidence: float
    explanation: str
    scores: dict[str, float]
