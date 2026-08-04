from __future__ import annotations

from typing import Any

from src.quality.evaluators.base import BaseQualityEvaluator
from src.repositories.claim import ClaimRepository
from src.repositories.dossier import ActivationDossierRepository


class ExportReadinessEvaluator(BaseQualityEvaluator):
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        dossier_repo = ActivationDossierRepository(self.session)
        dossier = dossier_repo.get_latest_for_analysis_run(analysis_run_id)
        dossier_exists = dossier is not None
        has_markdown = bool(dossier and dossier.dossier_markdown) if dossier else False

        claim_repo = ClaimRepository(self.session)
        coverage = claim_repo.get_evidence_coverage_summary(analysis_run_id)
        evidence_coverage = coverage.get("evidence_coverage", 0.0)
        unsupported_count = coverage.get("unsupported_claims", 0)

        dossier_score = 0.50 if dossier_exists and has_markdown else 0.0
        evidence_score = min(evidence_coverage, 1.0) * 0.50
        unsupported_penalty = 0.30 if unsupported_count > 0 else 0.0
        score = round(dossier_score + evidence_score - unsupported_penalty, 4)

        return {
            "export_readiness_score": max(0.0, score),
            "dossier_exists": dossier_exists,
            "has_markdown": has_markdown,
            "evidence_coverage": evidence_coverage,
            "unsupported_claim_count": unsupported_count,
        }
