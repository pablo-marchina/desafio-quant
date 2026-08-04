from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.quality.evaluators.base import BaseQualityEvaluator


class StructuredOutputReliabilityEvaluator(BaseQualityEvaluator):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def evaluate(self, analysis_run_id: str) -> dict[str, Any]:
        readiness_checks = self._get_readiness_checks_for_structured_output(analysis_run_id)
        readiness_checks_list = list(readiness_checks)

        invalid_count = sum(
            1
            for rc in readiness_checks_list
            if rc.code in ("STRUCTURED_OUTPUT_INVALID", "STRUCTURED_OUTPUT_RETRY_EXHAUSTED")
        )
        repaired_count = sum(1 for rc in readiness_checks_list if rc.code == "STRUCTURED_OUTPUT_REPAIRED")
        total = len(readiness_checks_list) if readiness_checks_list else 1

        return {
            "structured_output_valid_rate": (total - invalid_count) / total,
            "structured_output_repair_rate": repaired_count / total,
            "structured_output_failure_rate": invalid_count / total,
            "avg_retry_count": 0.0,
            "schema_validation_error_count": float(invalid_count),
            "missing_required_field_count": 0.0,
            "total_structured_output_checks": total,
        }

    def _get_readiness_checks_for_structured_output(self, analysis_run_id: str) -> list[Any]:
        from src.database.models import ProductReadinessCheck

        so_codes = {
            "STRUCTURED_OUTPUT_INVALID",
            "STRUCTURED_OUTPUT_REPAIRED",
            "STRUCTURED_OUTPUT_RETRY_EXHAUSTED",
            "STRUCTURED_OUTPUT_SCHEMA_DRIFT",
            "STRUCTURED_OUTPUT_MISSING_REQUIRED_FIELD",
        }
        return (
            self.session.query(ProductReadinessCheck)
            .filter(
                ProductReadinessCheck.analysis_run_id == analysis_run_id,
                ProductReadinessCheck.code.in_(so_codes),
            )
            .all()
        )
