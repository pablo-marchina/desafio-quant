"""Claim types, support levels, and review status constants."""

from __future__ import annotations

from enum import StrEnum


class ClaimType(StrEnum):
    ai_native_claim = "ai_native_claim"
    technical_stack_claim = "technical_stack_claim"
    market_claim = "market_claim"
    production_readiness_claim = "production_readiness_claim"
    defensibility_claim = "defensibility_claim"
    gap_claim = "gap_claim"
    nvidia_fit_claim = "nvidia_fit_claim"
    risk_claim = "risk_claim"
    activation_claim = "activation_claim"
    uncertainty_claim = "uncertainty_claim"


class SupportLevel(StrEnum):
    unsupported = "unsupported"
    weak = "weak"
    medium = "medium"
    strong = "strong"


class ClaimReviewStatus(StrEnum):
    unreviewed = "unreviewed"
    approved = "approved"
    rejected = "rejected"
    needs_more_evidence = "needs_more_evidence"


CRITICAL_CLAIM_TYPES = {
    ClaimType.gap_claim,
    ClaimType.defensibility_claim,
    ClaimType.nvidia_fit_claim,
    ClaimType.production_readiness_claim,
}
