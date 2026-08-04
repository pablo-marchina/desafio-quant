from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.database.models import ProductQualityMetric, ProductQualityRun
from src.quality.constants import (
    METRIC_ACTIVATION_PLAYBOOK_EVIDENCE_SUPPORT,
    METRIC_ACTIVATION_PLAYBOOK_PRESENT,
    METRIC_AVG_RETRY_COUNT,
    METRIC_DEGRADED_STATE_COUNT,
    METRIC_DOSSIER_SECTION_COMPLETENESS,
    METRIC_EVIDENCE_COVERAGE,
    METRIC_EXPORT_READINESS_SCORE,
    METRIC_MISSING_REQUIRED_FIELD_COUNT,
    METRIC_MISSING_REQUIRED_SECTIONS,
    METRIC_RECOMMENDATION_ACTIONABILITY_SCORE,
    METRIC_REVIEW_READINESS_SCORE,
    METRIC_SCHEMA_VALIDATION_ERROR_COUNT,
    METRIC_STRUCTURED_OUTPUT_FAILURE_RATE,
    METRIC_STRUCTURED_OUTPUT_REPAIR_RATE,
    METRIC_STRUCTURED_OUTPUT_VALID_RATE,
    METRIC_UNSUPPORTED_CLAIM_RATE,
    METRIC_UNSUPPORTED_CRITICAL_CLAIM_COUNT,
    METRIC_WEAK_CLAIM_RATE,
    THRESHOLDS,
)
from src.quality.evaluators.activation_playbook import ActivationPlaybookEvaluator
from src.quality.evaluators.degraded_state import DegradedStateEvaluator
from src.quality.evaluators.dossier_completeness import DossierCompletenessEvaluator
from src.quality.evaluators.evidence_coverage import EvidenceCoverageEvaluator
from src.quality.evaluators.export_readiness import ExportReadinessEvaluator
from src.quality.evaluators.recommendation_actionability import (
    RecommendationActionabilityEvaluator,
)
from src.quality.evaluators.review_readiness import ReviewReadinessEvaluator
from src.quality.evaluators.structured_output_reliability import (
    StructuredOutputReliabilityEvaluator,
)
from src.quality.repository import ProductQualityRepository
from src.repositories.product import ProductRepository


class ProductQualityService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ProductQualityRepository(session)
        self.product_repo = ProductRepository(session)

    def run_quality_evaluation_for_analysis_run(
        self,
        analysis_run_id: str,
    ) -> ProductQualityRun:
        run = self.product_repo.get_analysis_run(analysis_run_id)
        if run is None:
            raise LookupError(f"Analysis run not found: {analysis_run_id}")

        dossier_id = None
        action_brief_id = None
        dossiers = list(run.dossiers or [])
        if dossiers:
            latest = max(dossiers, key=lambda d: d.version)
            dossier_id = latest.id
        briefs = list(run.briefs or [])
        if briefs:
            latest_brief = max(briefs, key=lambda b: b.version)
            action_brief_id = latest_brief.id

        self.repository.delete_quality_runs_for_analysis_run(analysis_run_id)
        quality_run = self.repository.create_quality_run(
            analysis_run_id=analysis_run_id,
            dossier_id=dossier_id,
            action_brief_id=action_brief_id,
        )

        try:
            metrics = self._evaluate_all(analysis_run_id, quality_run.id)
            has_critical_failures = any(m.severity == "error" and not m.passed for m in metrics)
            has_warnings = any(m.severity == "warn" and not m.passed for m in metrics)

            if has_critical_failures:
                status = "degraded"
                reason = "One or more critical quality metrics failed thresholds"
            elif has_warnings:
                status = "completed"
                reason = None
            else:
                status = "completed"
                reason = None

            metrics_dict = {m.metric_name: m.metric_value for m in metrics}
            summary = self._build_summary(metrics)

            if status == "degraded":
                self.repository.degrade_quality_run(
                    quality_run.id,
                    degraded_reason=reason or "",
                    metrics_json=metrics_dict,
                    summary_json=summary,
                )
            else:
                self.repository.complete_quality_run(
                    quality_run.id,
                    metrics_json=metrics_dict,
                    summary_json=summary,
                )
        except Exception as exc:
            self.repository.fail_quality_run(
                quality_run.id,
                degraded_reason=f"Quality evaluation failed: {exc}",
            )

        self.session.commit()
        return quality_run

    def _evaluate_all(
        self,
        analysis_run_id: str,
        quality_run_id: str,
    ) -> list[ProductQualityMetric]:
        metrics: list[ProductQualityMetric] = []

        ev = EvidenceCoverageEvaluator(self.session)
        ev_result = ev.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_EVIDENCE_COVERAGE,
                ev_result.get("evidence_coverage", 0.0),
            )
        )
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_UNSUPPORTED_CLAIM_RATE,
                ev_result.get("unsupported_claim_rate", 0.0),
            )
        )
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_UNSUPPORTED_CRITICAL_CLAIM_COUNT,
                float(ev_result.get("unsupported_critical_claim_count", 0)),
            )
        )
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_WEAK_CLAIM_RATE,
                ev_result.get("weak_claim_rate", 0.0),
            )
        )

        dc = DossierCompletenessEvaluator(self.session)
        dc_result = dc.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_DOSSIER_SECTION_COMPLETENESS,
                dc_result.get("dossier_section_completeness", 0.0),
            )
        )
        missing_count = float(len(dc_result.get("missing_required_sections", [])))
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_MISSING_REQUIRED_SECTIONS,
                missing_count,
            )
        )

        ap = ActivationPlaybookEvaluator(self.session)
        ap_result = ap.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_ACTIVATION_PLAYBOOK_PRESENT,
                1.0 if ap_result.get("activation_playbook_present", False) else 0.0,
            )
        )
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_ACTIVATION_PLAYBOOK_EVIDENCE_SUPPORT,
                ap_result.get("activation_playbook_evidence_support", 0.0),
            )
        )

        ra = RecommendationActionabilityEvaluator(self.session)
        ra_result = ra.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_RECOMMENDATION_ACTIONABILITY_SCORE,
                ra_result.get("recommendation_actionability_score", 0.0),
            )
        )

        ds = DegradedStateEvaluator(self.session)
        ds_result = ds.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_DEGRADED_STATE_COUNT,
                float(ds_result.get("degraded_state_count", 0)),
            )
        )

        er = ExportReadinessEvaluator(self.session)
        er_result = er.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_EXPORT_READINESS_SCORE,
                er_result.get("export_readiness_score", 0.0),
            )
        )

        rr = ReviewReadinessEvaluator(self.session)
        rr_result = rr.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_REVIEW_READINESS_SCORE,
                rr_result.get("review_readiness_score", 0.0),
            )
        )

        so = StructuredOutputReliabilityEvaluator(self.session)
        so_result = so.evaluate(analysis_run_id)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_STRUCTURED_OUTPUT_VALID_RATE,
                so_result.get("structured_output_valid_rate", 1.0),
            )
        )
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_STRUCTURED_OUTPUT_REPAIR_RATE,
                so_result.get("structured_output_repair_rate", 0.0),
            )
        )
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_STRUCTURED_OUTPUT_FAILURE_RATE,
                so_result.get("structured_output_failure_rate", 0.0),
            )
        )
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_AVG_RETRY_COUNT,
                so_result.get("avg_retry_count", 0.0),
            )
        )
        error_count = so_result.get("schema_validation_error_count", 0)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_SCHEMA_VALIDATION_ERROR_COUNT,
                float(error_count),
            )
        )
        missing_count = so_result.get("missing_required_field_count", 0)
        metrics.append(
            self._make_metric(
                quality_run_id,
                METRIC_MISSING_REQUIRED_FIELD_COUNT,
                float(missing_count),
            )
        )

        self.repository.add_metrics_bulk(metrics)
        return metrics

    def _make_metric(
        self,
        quality_run_id: str,
        metric_name: str,
        metric_value: float,
    ) -> ProductQualityMetric:
        default_cfg = {"threshold": 0.0, "severity": "info", "operator": "gte"}
        threshold_config = THRESHOLDS.get(metric_name, default_cfg)
        threshold = threshold_config["threshold"]
        severity = threshold_config["severity"]
        operator = threshold_config.get("operator", "gte")

        if operator == "gte":
            passed = metric_value >= threshold
        elif operator == "lte":
            passed = metric_value <= threshold
        elif operator == "eq":
            passed = abs(metric_value - threshold) < 0.001
        else:
            passed = metric_value >= threshold

        return ProductQualityMetric(
            quality_run_id=quality_run_id,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            passed=passed,
            severity=severity,
            details_json={"operator": operator},
        )

    def _build_summary(self, metrics: list[ProductQualityMetric]) -> dict[str, Any]:
        total = len(metrics)
        passed = sum(1 for m in metrics if m.passed)
        failed = total - passed
        error_count = sum(1 for m in metrics if m.severity == "error" and not m.passed)
        warn_count = sum(1 for m in metrics if m.severity == "warn" and not m.passed)
        info_count = sum(1 for m in metrics if m.severity == "info" and not m.passed)

        metric_dict = {m.metric_name: m.metric_value for m in metrics}
        export_readiness = metric_dict.get(METRIC_EXPORT_READINESS_SCORE, 0.0)
        review_readiness = metric_dict.get(METRIC_REVIEW_READINESS_SCORE, 0.0)

        return {
            "total_metrics": total,
            "passed_metrics": passed,
            "failed_metrics": failed,
            "error_failures": error_count,
            "warn_failures": warn_count,
            "info_failures": info_count,
            "export_readiness_score": export_readiness,
            "review_readiness_score": review_readiness,
            "overall_status": ("degraded" if error_count > 0 else "warn" if warn_count > 0 else "pass"),
        }

    def evaluate_dossier(self, analysis_run_id: str) -> dict[str, Any]:
        dc = DossierCompletenessEvaluator(self.session)
        return dc.evaluate(analysis_run_id)

    def evaluate_action_brief(self, analysis_run_id: str) -> dict[str, Any]:
        ra = RecommendationActionabilityEvaluator(self.session)
        return ra.evaluate(analysis_run_id)

    def evaluate_claim_support(self, analysis_run_id: str) -> dict[str, Any]:
        ev = EvidenceCoverageEvaluator(self.session)
        return ev.evaluate(analysis_run_id)

    def evaluate_activation_recommendation(self, analysis_run_id: str) -> dict[str, Any]:
        ap = ActivationPlaybookEvaluator(self.session)
        return ap.evaluate(analysis_run_id)

    def evaluate_export_readiness(self, analysis_run_id: str) -> dict[str, Any]:
        er = ExportReadinessEvaluator(self.session)
        return er.evaluate(analysis_run_id)

    def evaluate_review_readiness(self, analysis_run_id: str) -> dict[str, Any]:
        rr = ReviewReadinessEvaluator(self.session)
        return rr.evaluate(analysis_run_id)

    def get_latest_quality_run(self, analysis_run_id: str) -> ProductQualityRun | None:
        return self.repository.get_latest_quality_run_for_analysis_run(analysis_run_id)

    def summarize_quality_result(self, analysis_run_id: str) -> dict[str, Any]:
        run = self.repository.get_latest_quality_run_for_analysis_run(analysis_run_id)
        if run is None:
            return {
                "analysis_run_id": analysis_run_id,
                "quality_run_id": None,
                "status": None,
                "evaluator_version": None,
                "overall_status": "no_quality_run",
                "total_metrics": 0,
                "passed_metrics": 0,
                "failed_metrics": 0,
                "export_readiness_score": None,
                "review_readiness_score": None,
                "metrics": {},
            }
        metrics = self.repository.get_metrics_for_quality_run(run.id)
        metric_dict = {m.metric_name: m.metric_value for m in metrics}
        metric_details = {
            m.metric_name: {
                "value": m.metric_value,
                "threshold": m.threshold,
                "passed": m.passed,
                "severity": m.severity,
            }
            for m in metrics
        }
        summary = run.summary_json or self._build_summary(metrics)
        export_readiness = summary.get("export_readiness_score") or metric_dict.get(METRIC_EXPORT_READINESS_SCORE)
        review_readiness = summary.get("review_readiness_score") or metric_dict.get(METRIC_REVIEW_READINESS_SCORE)

        return {
            "analysis_run_id": analysis_run_id,
            "quality_run_id": run.id,
            "status": run.status,
            "evaluator_version": run.evaluator_version,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "overall_status": summary.get("overall_status", "unknown"),
            "total_metrics": summary.get("total_metrics", len(metrics)),
            "passed_metrics": summary.get("passed_metrics", 0),
            "failed_metrics": summary.get("failed_metrics", 0),
            "export_readiness_score": export_readiness,
            "review_readiness_score": review_readiness,
            "degraded_reason": run.degraded_reason,
            "metrics": metric_details,
        }
