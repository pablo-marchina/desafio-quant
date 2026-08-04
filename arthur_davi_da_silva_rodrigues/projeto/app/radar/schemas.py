from dataclasses import dataclass


@dataclass(frozen=True)
class ThreatOpportunityRadar:
    wrapper_risk: float
    defensibility: float
    nvidia_fit: float
    outreach_urgency: float
    summary: str
    recommended_focus: tuple[str, ...]
