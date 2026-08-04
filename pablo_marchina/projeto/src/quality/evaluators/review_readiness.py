from __future__ import annotations

from typing import Any

from src.quality.evaluators.base import BaseQualityEvaluator
from src.repositories.claim import ClaimRepository
from src.repositories.product import ProductRepository
from src.repositories.review import ReviewDecisionRepository


class ReviewReadinessEvaluator(BaseQualityEvaluator):
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        repo = ProductRepository(self.session)
        run = repo.get_analysis_run(analysis_run_id)
        if run is None:
            return {
                "review_readiness_score": 0.0,
                "has_review": False,
                "unsupported_critical_count": 0,
            }

        review_repo = ReviewDecisionRepository(self.session)
        reviews = review_repo.list_for_run(analysis_run_id)
        has_review = len(reviews) > 0

        claim_repo = ClaimRepository(self.session)
        coverage = claim_repo.get_evidence_coverage_summary(analysis_run_id)
        evidence_coverage = coverage.get("evidence_coverage", 0.0)
        unsupported_count = coverage.get("unsupported_claims", 0)
        total_claims = coverage.get("total_claims", 0)

        has_review_score = 0.30 if has_review else 0.0
        evidence_score = min(evidence_coverage, 1.0) * 0.40
        unsupported_penalty = 0.30 if unsupported_count > 0 else 0.0

        run_completed = run.status in ("completed", "degraded")
        run_score = 0.30 if run_completed else 0.0

        score = round(has_review_score + evidence_score + run_score - unsupported_penalty, 4)

        return {
            "review_readiness_score": max(0.0, score),
            "has_review": has_review,
            "total_reviews": len(reviews),
            "evidence_coverage": evidence_coverage,
            "unsupported_claim_count": unsupported_count,
            "total_claims": total_claims,
            "run_status": run.status,
        }
