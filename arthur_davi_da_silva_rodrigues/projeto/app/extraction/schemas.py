from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceClaimDraft:
    claim: str
    claim_type: str
    supporting_text: str
    confidence: float
    validation_status: str


@dataclass(frozen=True)
class StartupProfileDraft:
    name: str | None
    website: str
    description: str | None
    ai_usage_summary: str | None
    sectors: tuple[str, ...]
    technology_signals: tuple[str, ...]
    evidence_claims: tuple[EvidenceClaimDraft, ...]
    accepted_claims: tuple[EvidenceClaimDraft, ...]
    review_claims: tuple[EvidenceClaimDraft, ...]
