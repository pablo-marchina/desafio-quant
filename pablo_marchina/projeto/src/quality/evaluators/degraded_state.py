from __future__ import annotations

from typing import Any

from src.quality.evaluators.base import BaseQualityEvaluator
from src.repositories.product import ProductRepository


class DegradedStateEvaluator(BaseQualityEvaluator):
    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        repo = ProductRepository(self.session)
        run = repo.get_analysis_run(analysis_run_id)
        if run is None:
            return {"degraded_state_count": 0, "checks": []}

        checks = list(run.readiness_checks or [])
        degraded = [
            {
                "code": c.code,
                "severity": c.severity,
                "status": c.status,
                "message": c.user_message,
            }
            for c in checks
            if c.status in ("degraded", "error")
        ]
        return {
            "degraded_state_count": len(degraded),
            "checks": degraded,
        }
