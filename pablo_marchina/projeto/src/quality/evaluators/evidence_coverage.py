from __future__ import annotations

from typing import Any

from src.quality.evaluators.base import BaseQualityEvaluator
from src.repositories.claim import ClaimRepository


class EvidenceCoverageEvaluator(BaseQualityEvaluator):
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        claim_repo = ClaimRepository(self.session)
        coverage = claim_repo.get_evidence_coverage_summary(analysis_run_id)
        return {
            "evidence_coverage": coverage.get("evidence_coverage", 0.0),
            "unsupported_claim_rate": coverage.get("unsupported_claim_rate", 0.0),
            "unsupported_critical_claim_count": (
                coverage.get("total_claims", 0) - coverage.get("critical_supported_claims", 0)
                if coverage.get("total_claims", 0) > 0
                else 0
            ),
            "weak_claim_rate": (
                coverage.get("weak_claims", 0) / coverage.get("total_claims", 1)
                if coverage.get("total_claims", 0) > 0
                else 0.0
            ),
            "total_claims": coverage.get("total_claims", 0),
            "supported_claims": coverage.get("supported_claims", 0),
            "unsupported_claims": coverage.get("unsupported_claims", 0),
            "weak_claims": coverage.get("weak_claims", 0),
            "critical_claims": coverage.get("critical_claims", 0),
        }
