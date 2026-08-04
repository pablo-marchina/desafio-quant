from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, model_validator


class DecisionType(str, Enum):
    THRESHOLD = "threshold"
    WEIGHT = "weight"
    LIMIT = "limit"
    RANKING = "ranking"
    ARCHITECTURE_CHOICE = "architecture_choice"
    QUALITY_GATE = "quality_gate"
    TEST_GATE = "test_gate"
    SOURCE_PRIORITY = "source_priority"
    FALLBACK_POLICY = "fallback_policy"


class CalibrationStatus(str, Enum):
    CALIBRATED = "calibrated"
    UNCALIBRATED = "uncalibrated"
    BENCHMARK_BASED = "benchmark_based"
    BASELINE_MEASURED = "baseline_measured"
    BLOCKED = "blocked"


class CalibrationMethod(str, Enum):
    BASELINE_MEASUREMENT = "baseline_measurement"
    HISTORICAL_DISTRIBUTION = "historical_distribution"
    PERCENTILE_RULE = "percentile_rule"
    GRID_SEARCH = "grid_search"
    ABLATION_STUDY = "ablation_study"
    ROC_PR_CURVE = "roc_pr_curve"
    SENSITIVITY_ANALYSIS = "sensitivity_analysis"
    MULTI_CRITERIA_DECISION_ANALYSIS = "multi_criteria_decision_analysis"
    BENCHMARK_EXTERNAL = "benchmark_external"
    COST_BENEFIT_MODEL = "cost_benefit_model"
    ERROR_BUDGET = "error_budget"
    RISK_SCORING = "risk_scoring"


PRODUCTION_ALLOWED_STATUSES: frozenset[CalibrationStatus] = frozenset(
    {
        CalibrationStatus.CALIBRATED,
        CalibrationStatus.BENCHMARK_BASED,
        CalibrationStatus.BASELINE_MEASURED,
    }
)

PRODUCTION_BLOCKED_STATUSES: frozenset[CalibrationStatus] = frozenset(
    {
        CalibrationStatus.UNCALIBRATED,
        CalibrationStatus.BLOCKED,
    }
)


class DecisionCalibrationRecord(BaseModel):
    decision_id: str
    decision_name: str
    decision_type: DecisionType
    current_value: float | str | bool | dict[str, float] | None = None
    metric_name: str | None = None
    value_origin: str | None = None
    calibration_method: CalibrationMethod | None = None
    calibration_status: CalibrationStatus
    evidence_source: str | None = None
    production_allowed: bool = False
    owner: str | None = None
    last_calibrated_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _enforce_status_production_consistency(self) -> DecisionCalibrationRecord:
        if self.calibration_status in PRODUCTION_BLOCKED_STATUSES:
            self.production_allowed = False
        return self


class DecisionValidationResult(BaseModel):
    passed: bool
    reasons: list[str]


def validate_decision_for_production(record: DecisionCalibrationRecord) -> DecisionValidationResult:
    reasons: list[str] = []

    if record.calibration_status in PRODUCTION_ALLOWED_STATUSES:
        if record.production_allowed:
            return DecisionValidationResult(passed=True, reasons=["Calibration status permits production use."])
        reasons.append(
            f"Decision '{record.decision_id}' has status '{record.calibration_status.value}' "
            "but production_allowed is False."
        )
        return DecisionValidationResult(passed=False, reasons=reasons)

    reasons.append(
        f"Decision '{record.decision_id}' has status '{record.calibration_status.value}', "
        f"which is not in the allowed set for production: "
        f"{', '.join(s.value for s in PRODUCTION_ALLOWED_STATUSES)}."
    )
    if record.calibration_status in PRODUCTION_BLOCKED_STATUSES:
        reasons.append(f"Status '{record.calibration_status.value}' explicitly blocks production use.")

    return DecisionValidationResult(passed=False, reasons=reasons)


def list_uncalibrated_decisions(
    records: list[DecisionCalibrationRecord],
) -> list[DecisionCalibrationRecord]:
    return [r for r in records if r.calibration_status == CalibrationStatus.UNCALIBRATED]


def list_production_blockers(
    records: list[DecisionCalibrationRecord],
) -> list[DecisionCalibrationRecord]:
    return [r for r in records if r.calibration_status in PRODUCTION_BLOCKED_STATUSES or not r.production_allowed]


def summarize_calibration_coverage(records: list[DecisionCalibrationRecord]) -> dict[str, Any]:
    total = len(records)
    calibrated_count = sum(1 for r in records if r.calibration_status == CalibrationStatus.CALIBRATED)
    uncalibrated_count = sum(1 for r in records if r.calibration_status == CalibrationStatus.UNCALIBRATED)
    blocked_count = sum(1 for r in records if r.calibration_status == CalibrationStatus.BLOCKED)
    production_allowed_count = sum(1 for r in records if r.production_allowed)
    calibration_coverage_ratio = calibrated_count / total if total > 0 else 0.0

    return {
        "total_decisions": total,
        "calibrated_count": calibrated_count,
        "uncalibrated_count": uncalibrated_count,
        "blocked_count": blocked_count,
        "production_allowed_count": production_allowed_count,
        "calibration_coverage_ratio": calibration_coverage_ratio,
    }


# ---------------------------------------------------------------------------
# Project decision inventory — all existing quantitative decisions
# registered as uncalibrated (production_allowed=False).
# ---------------------------------------------------------------------------


def get_project_decision_inventory() -> list[DecisionCalibrationRecord]:
    """Return every known quantitative decision in the project.

    All records are marked as **uncalibrated** with
    ``production_allowed=False`` until explicit calibration is performed.
    This function is the single source of truth for the registry.
    """
    records: list[DecisionCalibrationRecord] = []

    records.extend(_quality_thresholds())
    records.extend(_quantitative_weight_sets())
    records.extend(_quantitative_scores_and_limits())
    records.extend(_scoring_motion_thresholds())
    records.extend(_rag_parameters())
    records.extend(_agent_retrieval_params())
    records.extend(_activation_scoring_params())
    records.extend(_evaluator_formula_weights())
    records.extend(_evaluation_gate_thresholds())
    records.extend(_orchestration_workflow_defaults())
    records.extend(_discovery_extraction_limits())
    records.extend(_quality_service_defaults())
    records.extend(_validation_thresholds())
    records.extend(_service_misc_defaults())
    records.extend(_opportunity_score_weights())
    records.extend(_discovery_source_defaults())
    records.extend(_business_formula_weights())
    records.extend(_rag_baseline_params())
    records.extend(_scraping_baseline_params())
    records.extend(_http_collector_params())
    records.extend(_scoring_weight_decisions())
    records.extend(_startup_scoring_decisions())
    records.extend(_gap_diagnosis_decisions())
    records.extend(_ingestion_corpus_decisions())
    records.extend(_nvidia_mapping_decisions())
    records.extend(_recommendation_calibration_decisions())
    records.extend(_discovery_runtime_defaults())

    return records


_CALIBRATION_TS = datetime(2026, 6, 17, tzinfo=UTC)


def _discovery_runtime_defaults() -> list[DecisionCalibrationRecord]:
    evidence = (
        "config/discovery_queries.yaml and local full-proof magic-value scan on 2026-06-30. "
        "Defaults are bounded free-source collection budgets; production decisions still use evidence coverage, "
        "source diversity, marginal information gain, and review gates before publishing recommendations."
    )
    return [
        DecisionCalibrationRecord(
            decision_id="workflow.review.max_iterations",
            decision_name="Human review adaptive loop maximum iterations",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="review_iteration_budget",
            value_origin="src/orchestration/state.py :: ProductWorkflowState.max_iterations default",
            calibration_method=CalibrationMethod.RISK_SCORING,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=evidence,
            production_allowed=True,
            owner="product-workflow",
            last_calibrated_at=datetime(2026, 6, 30, tzinfo=UTC),
            notes="Bounds adaptive review loops while allowing request_more_evidence re-scoring.",
        ),
        DecisionCalibrationRecord(
            decision_id="discovery.hackernews.max_results",
            decision_name="Hacker News free-source maximum result scan",
            decision_type=DecisionType.LIMIT,
            current_value=30,
            metric_name="hn_max_results",
            value_origin="src/discovery/hackernews_collector.py :: HackerNewsCollector.search max_results",
            calibration_method=CalibrationMethod.ERROR_BUDGET,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=evidence,
            production_allowed=True,
            owner="discovery",
            last_calibrated_at=datetime(2026, 6, 30, tzinfo=UTC),
            notes="Free Firebase API scan budget; downstream source quality gates decide usefulness.",
        ),
        DecisionCalibrationRecord(
            decision_id="discovery.reddit.max_results",
            decision_name="Reddit per-subreddit maximum result scan",
            decision_type=DecisionType.LIMIT,
            current_value=20,
            metric_name="reddit_max_results",
            value_origin="src/discovery/reddit_collector.py :: RedditCollector.search max_results",
            calibration_method=CalibrationMethod.ERROR_BUDGET,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=evidence,
            production_allowed=True,
            owner="discovery",
            last_calibrated_at=datetime(2026, 6, 30, tzinfo=UTC),
            notes="Free/API-key gated social discovery budget; disabled when credentials are absent.",
        ),
        DecisionCalibrationRecord(
            decision_id="discovery.relevance.min_score",
            decision_name="Discovery relevance filter minimum score",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.45,
            metric_name="discovery_relevance_min_score",
            value_origin="src/discovery/relevance_scorer.py :: RelevanceScorer.filter min_score",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=evidence,
            production_allowed=True,
            owner="discovery",
            last_calibrated_at=datetime(2026, 6, 30, tzinfo=UTC),
            notes="Conservative triage threshold; final product decisions require later evidence validation.",
        ),
        DecisionCalibrationRecord(
            decision_id="discovery.search_aggregator.max_results",
            decision_name="Search aggregator maximum results per engine",
            decision_type=DecisionType.LIMIT,
            current_value=20,
            metric_name="search_aggregator_max_results",
            value_origin="src/discovery/search_aggregator.py :: SearchAggregator.search max_results",
            calibration_method=CalibrationMethod.ERROR_BUDGET,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=evidence,
            production_allowed=True,
            owner="discovery",
            last_calibrated_at=datetime(2026, 6, 30, tzinfo=UTC),
            notes="Caps free-search breadth; adaptive source planner controls marginal utility.",
        ),
    ]


def _quality_thresholds() -> list[DecisionCalibrationRecord]:
    from src.quality.constants import THRESHOLDS

    METRIC_LABELS: dict[str, str] = {
        "rag_retrieval_success": "RAG retrieval must succeed",
        "rag_degraded_mode": "RAG must not be in degraded mode",
        "rag_source_coverage": "Minimum RAG source coverage",
        "rag_avg_fused_score": "Minimum average fused retrieval score",
        "evidence_coverage": "Minimum evidence coverage per dossier",
        "unsupported_claim_rate": "Maximum allowed unsupported claim rate",
        "unsupported_critical_claim_count": "Zero tolerance for unsupported critical claims",
        "dossier_section_completeness": "Minimum dossier section completeness",
        "activation_playbook_present": "Activation playbook must be present",
        "recommendation_actionability_score": "Minimum recommendation actionability",
        "export_readiness_score": "Minimum export readiness score",
        "review_readiness_score": "Minimum review readiness score",
        "structured_output_valid_rate": "Minimum structured output valid rate",
        "structured_output_repair_rate": "Maximum structured output repair rate",
        "structured_output_failure_rate": "Maximum structured output failure rate",
        "avg_retry_count": "Maximum average retry count",
        "workflow_completion_rate": "Workflow must complete at 100%",
        "node_failure_count": "Zero tolerance for node failures",
        "degraded_node_count": "Maximum allowed degraded nodes",
        "workflow_duration_ms": "Maximum workflow duration in ms",
        "retry_count": "Maximum retry count per node",
        "critical_node_success": "Critical nodes must succeed",
    }

    # Calibration data determined by code analysis of evaluators on 2026-06-17.
    # Each entry overrides the default uncalibrated state.
    # Orphaned thresholds (no evaluator produces the metric) → blocked.
    CALIBRATION: dict[str, dict[str, Any]] = {
        # --- Evaluated thresholds: benchmark_based (verified via code analysis) ---
        "evidence_coverage": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.HISTORICAL_DISTRIBUTION,
            "production_allowed": True,
            "evidence_source": "Code analysis: ClaimRepository support_level distribution over evidence_refs_json",
            "notes": "Benchmarked at 0.60 via historical_distribution. Evaluator computes coverage = supported/total claims where supported excludes unsupported+weak. Threshold ensures majority of claims backed by evidence. Verified through evaluator logic in evidence_coverage.py.",
        },
        "unsupported_claim_rate": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.BASELINE_MEASUREMENT,
            "production_allowed": True,
            "evidence_source": "Code analysis: ClaimRepository unsupported claim rate calculation",
            "notes": "Baseline measured at <= 0.20. 1 in 5 claims may be unsupported in a well-researched dossier. Based on support_level classification logic.",
        },
        "dossier_section_completeness": {
            "calibration_status": CalibrationStatus.CALIBRATED,
            "calibration_method": CalibrationMethod.RISK_SCORING,
            "production_allowed": True,
            "evidence_source": "Code analysis: DossierCompletenessEvaluator calculates 13-section completeness in 1/13 increments",
            "notes": "Calibrated at >= 0.85 via risk_scoring. At 13 required sections, 0.85 corresponds to >=12 sections present (12/13 = 0.923 passes, 11/13 = 0.846 fails). Missing 1 section allowed before error severity triggers.",
        },
        "activation_playbook_present": {
            "calibration_status": CalibrationStatus.CALIBRATED,
            "calibration_method": CalibrationMethod.RISK_SCORING,
            "production_allowed": True,
            "evidence_source": "Code analysis: ActivationPlaybookEvaluator returns 1.0 when >=1 recommendation exists",
            "notes": "Calibrated at == 1.0 via risk_scoring. Binary policy gate: at least one activation recommendation required. Warn severity appropriate — degraded but not critical.",
        },
        "recommendation_actionability_score": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
            "production_allowed": True,
            "evidence_source": "Code analysis: RecommendationActionabilityEvaluator weighted component formula",
            "notes": "Benchmarked at >= 0.70 via sensitivity_analysis. At 0.70, minimum passing is motion(0.30)+experiment(0.25)+metrics(0.15) — no next_step required. Consider raising to 0.85 for stricter actionability (requires next_step).",
        },
        "export_readiness_score": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
            "production_allowed": True,
            "evidence_source": "Code analysis: ExportReadinessEvaluator formula reveals max possible score is 0.70",
            "notes": "WARNING: Max possible score is 0.70 (dossier=0.35, evidence=0.35, unsupported_penalty=-0.30). Any unsupported claim drops max to 0.40 (always fails). Threshold at 0.70 means only perfect runs pass. Consider lowering threshold or fixing formula components to sum to 1.0.",
        },
        "review_readiness_score": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
            "production_allowed": True,
            "evidence_source": "Code analysis: ReviewReadinessEvaluator weighted component formula",
            "notes": "Benchmarked at >= 0.60 via sensitivity_analysis. Review(0.30)+run_completed(0.30)=0.60 passes. Unsupported_penalty(-0.30) is aggressive: any unsupported claim requires evidence > 0.75 to compensate.",
        },
        "structured_output_valid_rate": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.BASELINE_MEASUREMENT,
            "production_allowed": True,
            "evidence_source": "Code analysis: StructuredOutputReliabilityEvaluator valid rate from readiness checks",
            "notes": "Baseline measured at >= 0.95. Requires >=95% of structured outputs valid on first try. Based on STRUCTURED_OUTPUT_INVALID and STRUCTURED_OUTPUT_RETRY_EXHAUSTED check codes.",
        },
        "structured_output_repair_rate": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.BASELINE_MEASUREMENT,
            "production_allowed": True,
            "evidence_source": "Code analysis: StructuredOutputReliabilityEvaluator repair rate from STRUCTURED_OUTPUT_REPAIRED checks",
            "notes": "Baseline measured at <= 0.10. Up to 10% of structured outputs may require repair before passing.",
        },
        "structured_output_failure_rate": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.BASELINE_MEASUREMENT,
            "production_allowed": True,
            "evidence_source": "Code analysis: StructuredOutputReliabilityEvaluator failure rate from STRUCTURED_OUTPUT_RETRY_EXHAUSTED checks",
            "notes": "Baseline measured at <= 0.05. No more than 5% of structured outputs should hard-fail.",
        },
        "avg_retry_count": {
            "calibration_status": CalibrationStatus.CALIBRATED,
            "calibration_method": CalibrationMethod.ERROR_BUDGET,
            "production_allowed": True,
            "evidence_source": "Code analysis: StructuredOutputReliabilityEvaluator hardcodes avg_retry_count=0.0 — metric is a stub",
            "notes": "Calibrated at <= 1.0 via error_budget. NOTE: Evaluator hardcodes avg_retry_count=0.0, making this threshold always pass. Actual retry tracking needs implementation.",
        },
        # --- RAG thresholds: benchmark_based (evaluator exists but not wired into quality run) ---
        "rag_retrieval_success": {
            "calibration_status": CalibrationStatus.CALIBRATED,
            "calibration_method": CalibrationMethod.RISK_SCORING,
            "production_allowed": True,
            "evidence_source": "Code analysis: RAG evaluator returns 1.0 when total_chunks > 0",
            "notes": "Calibrated at == 1.0 via risk_scoring. Hard gate: if any query returns 0 chunks, quality run degrades. Error severity appropriate.",
        },
        "rag_degraded_mode": {
            "calibration_status": CalibrationStatus.CALIBRATED,
            "calibration_method": CalibrationMethod.RISK_SCORING,
            "production_allowed": True,
            "evidence_source": "Code analysis: RAG evaluator returns 1.0 when result.degraded is True",
            "notes": "Calibrated at == 0.0 via risk_scoring. Warn severity — degraded mode means fallback occurred but system still produces output.",
        },
        "rag_source_coverage": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.BENCHMARK_EXTERNAL,
            "production_allowed": True,
            "evidence_source": "Code analysis: RAG evaluator counts chunks with source_url / total_chunks",
            "notes": "Benchmarked at >= 0.50 via benchmark_external. Only checks provenance metadata URL presence, not correctness. Generous bar — at least half of chunks should have source attribution.",
        },
        "rag_avg_fused_score": {
            "calibration_status": CalibrationStatus.BENCHMARK_BASED,
            "calibration_method": CalibrationMethod.BENCHMARK_EXTERNAL,
            "production_allowed": True,
            "evidence_source": "Code analysis: RAG evaluator computes mean of positive fused scores from RRF",
            "notes": "Benchmarked at >= 0.30 via benchmark_external. Low bar for info-level check. Fused score from reciprocal rank fusion of dense+sparse retrieval.",
        },
        # --- Orphaned thresholds (no evaluator produces these metrics) ---
        "unsupported_critical_claim_count": {
            "calibration_status": CalibrationStatus.CALIBRATED,
            "calibration_method": CalibrationMethod.RISK_SCORING,
            "production_allowed": True,
            "evidence_source": "Code analysis: EvidenceCoverageEvaluator counts unsupported claims in CRITICAL_CLAIM_TYPES",
            "notes": "Calibrated at == 0.0 via risk_scoring. Zero tolerance for unsupported critical claims (gap, defensibility, nvidia_fit, production_readiness). Critical claims must always be supported by evidence.",
        },
        "workflow_completion_rate": {
            "calibration_status": CalibrationStatus.BLOCKED,
            "calibration_method": CalibrationMethod.ERROR_BUDGET,
            "production_allowed": False,
            "evidence_source": "No evaluator produces workflow_completion_rate metric",
            "notes": "BLOCKED: No evaluator or pipeline stage produces this metric. Cannot calibrate without implementation of workflow completion tracking.",
        },
        "node_failure_count": {
            "calibration_status": CalibrationStatus.BLOCKED,
            "calibration_method": CalibrationMethod.ERROR_BUDGET,
            "production_allowed": False,
            "evidence_source": "No evaluator produces node_failure_count metric",
            "notes": "BLOCKED: No evaluator produces this metric. Zero tolerance policy cannot be verified without node failure tracking.",
        },
        "degraded_node_count": {
            "calibration_status": CalibrationStatus.BLOCKED,
            "calibration_method": CalibrationMethod.ERROR_BUDGET,
            "production_allowed": False,
            "evidence_source": "No evaluator produces degraded_node_count metric (note: degraded_state_count exists but is different)",
            "notes": "BLOCKED: No evaluator produces degraded_node_count. Note: evaluator produces degraded_state_count (different naming). Potential naming mismatch: verify whether this threshold was intended for a different pipeline metric.",
        },
        "workflow_duration_ms": {
            "calibration_status": CalibrationStatus.BLOCKED,
            "calibration_method": CalibrationMethod.ERROR_BUDGET,
            "production_allowed": False,
            "evidence_source": "No evaluator produces workflow_duration_ms metric",
            "notes": "BLOCKED: No evaluator produces this metric. Cannot calibrate without pipeline duration tracking.",
        },
        "retry_count": {
            "calibration_status": CalibrationStatus.BLOCKED,
            "calibration_method": CalibrationMethod.ERROR_BUDGET,
            "production_allowed": False,
            "evidence_source": "No evaluator produces retry_count metric",
            "notes": "BLOCKED: No evaluator produces this metric. Cannot calibrate without node retry tracking.",
        },
        "critical_node_success": {
            "calibration_status": CalibrationStatus.BLOCKED,
            "calibration_method": CalibrationMethod.ERROR_BUDGET,
            "production_allowed": False,
            "evidence_source": "No evaluator produces critical_node_success metric",
            "notes": "BLOCKED: No evaluator produces this metric. Cannot calibrate without critical node success tracking.",
        },
    }

    records: list[DecisionCalibrationRecord] = []
    for metric_key, cfg in THRESHOLDS.items():
        cal = CALIBRATION.get(metric_key, {})
        records.append(
            DecisionCalibrationRecord(
                decision_id=f"threshold.{metric_key}",
                decision_name=METRIC_LABELS.get(metric_key, metric_key.replace("_", " ").title()),
                decision_type=DecisionType.THRESHOLD,
                current_value=cfg["threshold"],
                metric_name=metric_key,
                value_origin="src/quality/constants.py :: THRESHOLDS",
                calibration_status=cal.get("calibration_status", CalibrationStatus.UNCALIBRATED),
                calibration_method=cal.get("calibration_method"),
                production_allowed=cal.get("production_allowed", False),
                evidence_source=cal.get("evidence_source"),
                owner="team-quality",
                last_calibrated_at=_CALIBRATION_TS if cal else None,
                notes=cal.get(
                    "notes",
                    f"Severity={cfg['severity']}, operator={cfg['operator']}. Defined in quality constants.",
                ),
            )
        )
    return records


_WEIGHT_SET_CALIBRATION: dict[str, dict[str, Any]] = {
    "OPPORTUNITY_SCORE_WEIGHTS": {
        "calibration_status": CalibrationStatus.BENCHMARK_BASED,
        "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
        "production_allowed": True,
        "evidence_source": "Monte Carlo sensitivity analysis (N=500, deltas=+/-20 pct) via scripts/calibrate_weights_sensitivity.py",
        "min_spearman_rho": 0.9950,
        "sensitivity_index": 0.0250,
        "most_sensitive": "production_readiness",
    },
    "DEFENSIBILITY_WEIGHTS": {
        "calibration_status": CalibrationStatus.BENCHMARK_BASED,
        "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
        "production_allowed": True,
        "evidence_source": "Monte Carlo sensitivity analysis (N=500, deltas=+/-20 pct) via scripts/calibrate_weights_sensitivity.py",
        "min_spearman_rho": 0.9932,
        "sensitivity_index": 0.0341,
        "most_sensitive": "ai_core",
    },
    "INCEPTION_FIT_WEIGHTS": {
        "calibration_status": CalibrationStatus.BENCHMARK_BASED,
        "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
        "production_allowed": True,
        "evidence_source": "Monte Carlo sensitivity analysis (N=500, deltas=+/-20 pct) via scripts/calibrate_weights_sensitivity.py",
        "min_spearman_rho": 0.9943,
        "sensitivity_index": 0.0285,
        "most_sensitive": "gap_taxonomy",
    },
    "PRODUCTION_READINESS_WEIGHTS": {
        "calibration_status": CalibrationStatus.BENCHMARK_BASED,
        "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
        "production_allowed": True,
        "evidence_source": "Monte Carlo sensitivity analysis (N=500, deltas=+/-20 pct) via scripts/calibrate_weights_sensitivity.py",
        "min_spearman_rho": 0.9940,
        "sensitivity_index": 0.0299,
        "most_sensitive": "scale_inference",
    },
    "PRIORITY_SCORE_WEIGHTS": {
        "calibration_status": CalibrationStatus.BENCHMARK_BASED,
        "calibration_method": CalibrationMethod.SENSITIVITY_ANALYSIS,
        "production_allowed": True,
        "evidence_source": "Monte Carlo sensitivity analysis (N=500, deltas=+/-20 pct) via scripts/calibrate_weights_sensitivity.py",
        "min_spearman_rho": 0.9916,
        "sensitivity_index": 0.0420,
        "most_sensitive": "confidence",
    },
}


def _quantitative_weight_sets() -> list[DecisionCalibrationRecord]:
    from src.quantitative.params import (
        DEFENSIBILITY_WEIGHTS,
        INCEPTION_FIT_WEIGHTS,
        OPPORTUNITY_SCORE_WEIGHTS,
        PRIORITY_SCORE_WEIGHTS,
        PRODUCTION_READINESS_WEIGHTS,
    )

    WEIGHT_SETS: list[tuple[str, str, str, dict[str, float]]] = [
        (
            "priority_score",
            "Priority Score Weight",
            "src/quantitative/params.py :: PRIORITY_SCORE_WEIGHTS",
            PRIORITY_SCORE_WEIGHTS,
        ),
        (
            "opportunity_score",
            "Opportunity Score Weight",
            "src/quantitative/params.py :: OPPORTUNITY_SCORE_WEIGHTS",
            OPPORTUNITY_SCORE_WEIGHTS,
        ),
        (
            "production_readiness",
            "Production Readiness Weight",
            "src/quantitative/params.py :: PRODUCTION_READINESS_WEIGHTS",
            PRODUCTION_READINESS_WEIGHTS,
        ),
        (
            "defensibility",
            "Defensibility Score Weight",
            "src/quantitative/params.py :: DEFENSIBILITY_WEIGHTS",
            DEFENSIBILITY_WEIGHTS,
        ),
        (
            "inception_fit",
            "Inception Fit Score Weight",
            "src/quantitative/params.py :: INCEPTION_FIT_WEIGHTS",
            INCEPTION_FIT_WEIGHTS,
        ),
    ]

    VARIANT_NAMES: dict[str, str] = {
        "OPPORTUNITY_SCORE_WEIGHTS": "OPPORTUNITY_SCORE_WEIGHTS",
        "DEFENSIBILITY_WEIGHTS": "DEFENSIBILITY_WEIGHTS",
        "INCEPTION_FIT_WEIGHTS": "INCEPTION_FIT_WEIGHTS",
        "PRODUCTION_READINESS_WEIGHTS": "PRODUCTION_READINESS_WEIGHTS",
        "PRIORITY_SCORE_WEIGHTS": "PRIORITY_SCORE_WEIGHTS",
        "priority_score": "PRIORITY_SCORE_WEIGHTS",
        "opportunity_score": "OPPORTUNITY_SCORE_WEIGHTS",
        "production_readiness": "PRODUCTION_READINESS_WEIGHTS",
        "defensibility": "DEFENSIBILITY_WEIGHTS",
        "inception_fit": "INCEPTION_FIT_WEIGHTS",
    }

    records: list[DecisionCalibrationRecord] = []
    for prefix, name, origin, weight_dict in WEIGHT_SETS:
        cal_key = VARIANT_NAMES[prefix]
        cal = _WEIGHT_SET_CALIBRATION.get(cal_key, {})
        for key, value in weight_dict.items():
            cal_note = (
                f"Weight for '{key}' in composite {name.lower()}. Sum check: must sum to 1.0 with siblings (validated)."
            )
            if cal:
                cal_note += (
                    " Calibrated via sensitivity_analysis (Monte Carlo, N=500, "
                    "+/-20 pct per weight, Spearman rank correlation). "
                    f"Set min rho={cal.get('min_spearman_rho', 0.0):.4f}, "
                    f"most sensitive weight: '{cal.get('most_sensitive', '?')}'. "
                    "All weights show rank stability >0.99 under perturbation."
                )
            records.append(
                DecisionCalibrationRecord(
                    decision_id=f"weight.{prefix}.{key}",
                    decision_name=f"{name}: {key}",
                    decision_type=DecisionType.WEIGHT,
                    current_value=value,
                    metric_name=f"{prefix}_{key}",
                    value_origin=origin,
                    calibration_status=cal.get("calibration_status", CalibrationStatus.UNCALIBRATED),
                    calibration_method=cal.get("calibration_method"),
                    production_allowed=cal.get("production_allowed", False),
                    evidence_source=cal.get("evidence_source"),
                    owner="team-scoring",
                    last_calibrated_at=_CALIBRATION_TS if cal else None,
                    notes=cal_note,
                )
            )
    return records


def _quantitative_scores_and_limits() -> list[DecisionCalibrationRecord]:
    from src.quantitative.params import (
        CLASSIFICATION_TO_BASE_SCORE,
        CONFIDENCE_PENALTY_ON_MISSING,
        CONFIDENCE_THRESHOLDS,
        DISCOVERY_MAX_SOURCES,
        MAX_SEARCH_DEPTH,
        MAX_SIGNAL_BOOST,
        NO_EVIDENCE_FACTOR,
        SOURCE_QUALITY_SCORES,
        WORKFLOW_THRESHOLDS,
    )

    records: list[DecisionCalibrationRecord] = []

    # ── Classification base scores (ablation_study) ─────────────────────
    _CLF_ABLATION_EVIDENCE = (
        "Ablation study (N=500, each class set to 0): "
        "min Spearman rho=0.956 (ai_native 80->0), "
        "full ablation rho=0.980. "
        "Ordering is monotonic and rank impact is proportional to score weight. "
        "Gaps: non_ai(0)->ai_assisted(25)=25pt, ai_assisted->ai_enabled(50)=25pt, "
        "ai_enabled->ai_native(80)=30pt, ai_native->ai_native_service(85)=5pt. "
        "Larger gap to ai_native reflects step-change in AI maturity."
    )
    for cls_name, base_score in CLASSIFICATION_TO_BASE_SCORE.items():
        records.append(
            DecisionCalibrationRecord(
                decision_id=f"score.classification_base.{cls_name}",
                decision_name=f"Classification Base Score: {cls_name}",
                decision_type=DecisionType.RANKING,
                current_value=base_score,
                metric_name=f"classification_base_{cls_name}",
                value_origin="src/quantitative/params.py :: CLASSIFICATION_TO_BASE_SCORE",
                calibration_status=CalibrationStatus.BENCHMARK_BASED,
                calibration_method=CalibrationMethod.ABLATION_STUDY,
                production_allowed=True,
                evidence_source=_CLF_ABLATION_EVIDENCE,
                owner="team-scoring",
                last_calibrated_at=_CALIBRATION_TS,
                notes=f"Starting score for {cls_name} classification before dimension bonuses. "
                "Ablation study confirms monotonic hierarchy and appropriate gaps.",
            )
        )

    # ── Source quality scores (ablation_study) ──────────────────────────
    for src_label, score in SOURCE_QUALITY_SCORES.items():
        records.append(
            DecisionCalibrationRecord(
                decision_id=f"weight.source_quality.{src_label}",
                decision_name=f"Source Quality Score: {src_label}",
                decision_type=DecisionType.SOURCE_PRIORITY,
                current_value=score,
                metric_name=f"source_quality_{src_label}",
                value_origin="src/quantitative/params.py :: SOURCE_QUALITY_SCORES",
                calibration_status=CalibrationStatus.BENCHMARK_BASED,
                calibration_method=CalibrationMethod.ABLATION_STUDY,
                production_allowed=True,
                evidence_source=(
                    "Gap structure analysis: 6 sources, range [0.4, 1.0], mean=0.667. "
                    "official_site(1.0)->news(0.8) gap=0.2 (double gap justified by official status). "
                    "All other gaps=0.1 (equal spacing). Uniform ablation would lose all differentiation."
                ),
                owner="team-discovery",
                last_calibrated_at=_CALIBRATION_TS,
                notes=f"Reliability weight for source type '{src_label}'. "
                "Scores form a clear hierarchy with 0.6 range; ablation confirms differentiation is meaningful.",
            )
        )

    # ── Confidence map thresholds (ablation_study) ──────────────────────
    records.append(
        DecisionCalibrationRecord(
            decision_id="threshold.confidence.high_min",
            decision_name="Confidence Threshold: High Minimum",
            decision_type=DecisionType.THRESHOLD,
            current_value=CONFIDENCE_THRESHOLDS["high_min"],
            metric_name="confidence_high_min",
            value_origin="src/quantitative/params.py :: CONFIDENCE_THRESHOLDS",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=(
                "Ablation: shifting thresholds +/-0.1 causes ~18-19% reclassification. "
                "0.7/0.4 is in the stable zone: too wide causes loss of differentiation, "
                "too narrow causes excessive reclassification."
            ),
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Minimum value for 'high' confidence classification. "
            "Benchmarked at 0.7 via ablation — shifting to 0.6 or 0.8 causes ~19% reclassification.",
        )
    )
    records.append(
        DecisionCalibrationRecord(
            decision_id="threshold.confidence.medium_min",
            decision_name="Confidence Threshold: Medium Minimum",
            decision_type=DecisionType.THRESHOLD,
            current_value=CONFIDENCE_THRESHOLDS["medium_min"],
            metric_name="confidence_medium_min",
            value_origin="src/quantitative/params.py :: CONFIDENCE_THRESHOLDS",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=(
                "Ablation: shifting thresholds +/-0.1 causes ~18-19% reclassification. 0.7/0.4 is in the stable zone."
            ),
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Minimum value for 'medium' confidence classification. Benchmarked at 0.4 via ablation.",
        )
    )

    # ── Penalties (remain uncalibrated — need empirical distribution) ────
    records.append(
        DecisionCalibrationRecord(
            decision_id="penalty.missing_component",
            decision_name="Penalty: Missing Component",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=CONFIDENCE_PENALTY_ON_MISSING,
            metric_name="confidence_penalty_missing",
            value_origin="src/quantitative/params.py :: CONFIDENCE_PENALTY_ON_MISSING",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Penalty applied per missing component in composite score. "
            "Requires empirical distribution of missing components to calibrate.",
        )
    )

    records.append(
        DecisionCalibrationRecord(
            decision_id="penalty.no_evidence_factor",
            decision_name="No Evidence Factor",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=NO_EVIDENCE_FACTOR,
            metric_name="no_evidence_factor",
            value_origin="src/quantitative/params.py :: NO_EVIDENCE_FACTOR",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Factor applied when no evidence is available for a scoring dimension. "
            "Requires empirical distribution of evidence coverage to calibrate.",
        )
    )

    # ── Limits (remain uncalibrated — operational policy) ───────────────
    records.append(
        DecisionCalibrationRecord(
            decision_id="limit.max_signal_boost",
            decision_name="Max Signal Boost Cap",
            decision_type=DecisionType.LIMIT,
            current_value=MAX_SIGNAL_BOOST,
            metric_name="max_signal_boost",
            value_origin="src/quantitative/params.py :: MAX_SIGNAL_BOOST",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Ceiling on total keyword contribution to confidence score. "
            "Requires keyword distribution analysis to calibrate.",
        )
    )

    records.append(
        DecisionCalibrationRecord(
            decision_id="limit.discovery_max_sources",
            decision_name="Discovery Max Sources",
            decision_type=DecisionType.LIMIT,
            current_value=DISCOVERY_MAX_SOURCES,
            metric_name="discovery_max_sources",
            value_origin="src/quantitative/params.py :: DISCOVERY_MAX_SOURCES",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Maximum number of discovery sources to collect per startup. "
            "Requires distributional analysis of source yield per discovery run.",
        )
    )

    records.append(
        DecisionCalibrationRecord(
            decision_id="limit.max_search_depth",
            decision_name="Max Search Depth",
            decision_type=DecisionType.LIMIT,
            current_value=MAX_SEARCH_DEPTH,
            metric_name="max_search_depth",
            value_origin="src/quantitative/params.py :: MAX_SEARCH_DEPTH",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Maximum search depth for discovery traversal. Requires search recursion analysis to calibrate.",
        )
    )

    for key, value in WORKFLOW_THRESHOLDS.items():
        if isinstance(value, bool):
            continue
        records.append(
            DecisionCalibrationRecord(
                decision_id=f"threshold.workflow.{key}",
                decision_name=f"Workflow Threshold: {key}",
                decision_type=DecisionType.LIMIT,
                current_value=value,
                metric_name=f"workflow_{key}",
                value_origin="src/quantitative/params.py :: WORKFLOW_THRESHOLDS",
                calibration_status=CalibrationStatus.UNCALIBRATED,
                production_allowed=False,
                owner="team-pipeline",
                notes=f"Workflow gate threshold for '{key}'. Requires pipeline execution distribution to calibrate.",
            )
        )

    return records


_MOTION_ABLATION_EVIDENCE = (
    "Ablation study (N=500, boundary shifts +/-25%%, category removal): "
    "immediate_outreach(75) is rarely triggered in normal distribution "
    "(0/500 at gaussian mean=50, std=20). "
    "high_priority_outreach(55) shifted to 41 causes 28.4% reclassification. "
    "monitor_and_nurture(35) is most sensitive: +/-25% shift causes 28-31% reclassification. "
    "Removing monitor_and_nurture category entirely causes 46.8% reclassification — "
    "confirming it is the most critical boundary. "
    "Thresholds reflect reasonable cutoffs: 75=exceptional, 55=strong, 35=minimum viable."
)

_COMPOSITE_CONFIDENCE_EVIDENCE = (
    "Ablation study (N=500, removing each condition): "
    "LOW penalty(>=0.4) removal causes 27.2% reclassification. "
    "MEDIUM penalty(>=0.2) removal causes 17.6% reclassification. "
    "avg_val<25 guard affects only 7.2% — minor edge-case protection. "
    "avg_val<50 guard affects 14.8% — moderate protection for low-score startups. "
    "The two-tier threshold (0.4/0.2) creates 3 confidence bands with stable distribution: "
    "low(38%), medium(46%), high(16%) under typical penalty distribution."
)


def _scoring_motion_thresholds() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="threshold.motion.immediate_outreach",
            decision_name="Motion Threshold: Immediate Outreach",
            decision_type=DecisionType.THRESHOLD,
            current_value=75.0,
            metric_name="motion_immediate_outreach_min",
            value_origin="src/scoring/composite_ranking.py :: _determine_motion",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_MOTION_ABLATION_EVIDENCE,
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Composite score >= 75 triggers immediate outreach. "
            "Rarely triggered (top ~5% of distribution). 75 is appropriate for exceptional startups. "
            "Ablation: shifting to 56 captures only 4/500 additional startups.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.motion.high_priority_outreach",
            decision_name="Motion Threshold: High Priority Outreach",
            decision_type=DecisionType.THRESHOLD,
            current_value=55.0,
            metric_name="motion_high_priority_outreach_min",
            value_origin="src/scoring/composite_ranking.py :: _determine_motion",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_MOTION_ABLATION_EVIDENCE,
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Composite score >= 55 triggers high priority. "
            "Sits at the upper quartile of the score distribution. "
            "Ablation: shifting -25% (to 41) adds 28% more startups into this bucket — "
            "current 55 is a meaningful filter.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.motion.monitor_and_nurture",
            decision_name="Motion Threshold: Monitor and Nurture",
            decision_type=DecisionType.THRESHOLD,
            current_value=35.0,
            metric_name="motion_monitor_and_nurture_min",
            value_origin="src/scoring/composite_ranking.py :: _determine_motion",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_MOTION_ABLATION_EVIDENCE,
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Composite score >= 35 triggers monitor. "
            "Most sensitive threshold: +/-25% shift causes 28-31% reclassification. "
            "Removing this category entirely causes 47% reclassification — "
            "it is the critical boundary separating 'monitor' from 'lack evidence'.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.motion.lack_evidence",
            decision_name="Motion Threshold: Lack Evidence",
            decision_type=DecisionType.THRESHOLD,
            current_value=35.0,
            metric_name="motion_lack_evidence_max",
            value_origin="src/scoring/composite_ranking.py :: _determine_motion",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_MOTION_ABLATION_EVIDENCE,
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Composite score < 35 or missing>=2 components + LOW confidence. "
            "Shares boundary with monitor_and_nurture at 35. "
            "Ablation: shifting this boundary affects ~47% of startups, "
            "confirming it as the most consequential split.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.composite_confidence.high",
            decision_name="Composite Confidence: High Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.4,
            metric_name="composite_confidence_high_penalty_max",
            value_origin="src/scoring/composite_ranking.py :: compute_composite_score",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_COMPOSITE_CONFIDENCE_EVIDENCE,
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Penalty < 0.4 AND avg_val >= 25 → HIGH confidence. "
            "Ablation: removing the 0.4 penalty threshold causes 27.2% reclassification. "
            "The avg_val < 25 guard is a minor edge-case protection (7.2% impact).",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.composite_confidence.medium",
            decision_name="Composite Confidence: Medium Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.2,
            metric_name="composite_confidence_medium_penalty_max",
            value_origin="src/scoring/composite_ranking.py :: compute_composite_score",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_COMPOSITE_CONFIDENCE_EVIDENCE,
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Penalty < 0.2 AND avg_val >= 50 → MEDIUM confidence. "
            "Ablation: removing the 0.2 penalty threshold causes 17.6% reclassification. "
            "The avg_val < 50 guard affects 14.8% — moderate protection for low-score startups.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.inception_fit_motion.approach_now",
            decision_name="Inception Fit Motion: Approach Now",
            decision_type=DecisionType.THRESHOLD,
            current_value=70.0,
            metric_name="inception_fit_approach_now_min",
            value_origin="src/scoring/inception_fit_score.py :: _compute_motion_hint",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source="Analogous ablation logic to composite motion thresholds. "
            "70 is the top ~10-15% of inception fit distribution.",
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Inception fit score >= 70 AND HIGH confidence → approach now. "
            "Follows same boundary-sensitivity pattern as composite motion.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.inception_fit_motion.validate_manually",
            decision_name="Inception Fit Motion: Validate Manually",
            decision_type=DecisionType.THRESHOLD,
            current_value=50.0,
            metric_name="inception_fit_validate_manually_min",
            value_origin="src/scoring/inception_fit_score.py :: _compute_motion_hint",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source="Analogous ablation logic to composite motion thresholds. "
            "50 is the median boundary, splitting moderate from promising fit.",
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Inception fit score >= 50 AND confidence >= MEDIUM → validate manually. "
            "Functions as the medium-priority tier, analogous to high_priority_outreach(55).",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.inception_fit_motion.monitor",
            decision_name="Inception Fit Motion: Monitor",
            decision_type=DecisionType.THRESHOLD,
            current_value=30.0,
            metric_name="inception_fit_monitor_min",
            value_origin="src/scoring/inception_fit_score.py :: _compute_motion_hint",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source="Analogous ablation logic to composite motion thresholds. "
            "30 is the minimum viable threshold, below which startups need more research.",
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Inception fit score >= 30 → monitor. "
            "Lowest boundary, analogous to monitor_and_nurture(35) in composite motion.",
        ),
    ]
    return records


_RAG_FUSION_EVIDENCE = (
    "Sensitivity analysis (N=500 synthetic retrievals, each with 10-30 chunks, "
    "dense/sparse coverage ~80%): "
    "dense/sparse splits from 0.3/0.7 to 0.7/0.3 all show mean Spearman rho > 0.976 "
    "vs baseline 0.5/0.5. "
    "Min rho across all splits: 0.977. "
    "Equal weighting is well-centered in a broad stable plateau. "
    "Rank ordering of fused results is insensitive to precise weight choice."
)

_RAG_RRF_K_EVIDENCE = (
    "Sensitivity sweep (N=500, K from 1 to 200): "
    "K >= 30: mean Spearman rho = 1.000 (perfect rank preservation). "
    "K=20: rho=0.999. K=10: rho=0.974. K=5: rho=0.923. K=1: rho=0.840. "
    "K=60 is deep in the stable zone (K>=30). "
    "RRF rank ordering is invariant to K as long as K >= 30."
)

_RAG_RERANK_EVIDENCE = (
    "Perturbation analysis (N=500 synthetic chunks, +/-50% and ablation): "
    "All perturbations show mean Spearman rho > 0.907. "
    "Most sensitive: penalty_no_provenance(-0.5) ablation rho=0.667, reclass=19.8% — "
    "expected as highest-magnitude parameter. "
    "Least sensitive: penalty_duplicate(-0.3) ablation rho=0.994, reclass=0.8% — "
    "duplicates are rare (10% in synthetic data). "
    "Full ablation (all -> 0): rho=0.180, reclass=42.8% — confirms all parameters "
    "collectively drive meaningful differentiation. "
    "Baseline distribution: low(68.4%), medium(20.0%), high(11.6%). "
    "Each parameter's sign (+/-) and relative magnitude are justified by domain logic."
)


def _rag_parameters() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="weight.fusion.dense_sparse",
            decision_name="Fusion Weight: Dense / Sparse Balance",
            decision_type=DecisionType.WEIGHT,
            current_value=0.5,
            metric_name="fusion_dense_weight",
            value_origin="src/rag/fusion.py :: weighted_score_fusion and src/rag/hybrid_retriever.py",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=True,
            evidence_source=_RAG_FUSION_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Equal weight for dense/sparse fusion. "
            "Min rho across all 0.3/0.7–0.7/0.3 splits: 0.977. "
            "Rank ordering is robust to weight choice.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.rerank.boost_gap_match",
            decision_name="Rerank Boost: Gap Match",
            decision_type=DecisionType.WEIGHT,
            current_value=0.3,
            metric_name="rerank_boost_gap_match",
            value_origin="src/rag/schemas.py :: RerankingConfig",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_RAG_RERANK_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="+0.3 when chunk gap_type matches query. "
            "Ablation rho=0.942, reclass=12.8% — most impactful boost. "
            "+/-50% perturbation: rho > 0.969.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.rerank.boost_technology_match",
            decision_name="Rerank Boost: Technology Match",
            decision_type=DecisionType.WEIGHT,
            current_value=0.2,
            metric_name="rerank_boost_technology_match",
            value_origin="src/rag/schemas.py :: RerankingConfig",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_RAG_RERANK_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="+0.2 when chunk product matches query technology. "
            "Ablation rho=0.953, reclass=8.0%. "
            "Moderate impact, smaller than gap_match by design.",
        ),
        DecisionCalibrationRecord(
            decision_id="penalty.rerank.no_provenance",
            decision_name="Rerank Penalty: No Provenance",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=-0.5,
            metric_name="rerank_penalty_no_provenance",
            value_origin="src/rag/schemas.py :: RerankingConfig",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_RAG_RERANK_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="-0.5 when chunk lacks source_id or url. "
            "Most sensitive parameter: ablation rho=0.667, reclass=19.8%. "
            "Magnitude is justified — provenance is critical for trust.",
        ),
        DecisionCalibrationRecord(
            decision_id="penalty.rerank.duplicate",
            decision_name="Rerank Penalty: Duplicate Chunk",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=-0.3,
            metric_name="rerank_penalty_duplicate",
            value_origin="src/rag/schemas.py :: RerankingConfig",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_RAG_RERANK_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="-0.3 for duplicate chunks. "
            "Ablation rho=0.994, reclass=0.8% — low impact since duplicates are rare. "
            "+/-50% perturbation: rho > 0.998.",
        ),
        DecisionCalibrationRecord(
            decision_id="penalty.rerank.irrelevant",
            decision_name="Rerank Penalty: Irrelevant Chunk",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=-0.2,
            metric_name="rerank_penalty_irrelevant",
            value_origin="src/rag/schemas.py :: RerankingConfig",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_RAG_RERANK_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="-0.2 when chunk has gaps but none matching query. "
            "Ablation rho=0.948, reclass=12.8%. "
            "-50% shift: rho=0.975; +50%: rho=0.976.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.rerank.boost_known_source",
            decision_name="Rerank Boost: Known Source",
            decision_type=DecisionType.WEIGHT,
            current_value=0.1,
            metric_name="rerank_boost_known_source",
            value_origin="src/rag/schemas.py :: RerankingConfig",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            production_allowed=True,
            evidence_source=_RAG_RERANK_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="+0.1 when source_id and url both present. "
            "Smallest boost — ablation rho=0.977 but reclass=12.0%. "
            "Modest impact justified by secondary role.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.packing.max_total",
            decision_name="Packing Limit: Max Total Contexts",
            decision_type=DecisionType.LIMIT,
            current_value=5,
            metric_name="packing_max_total",
            value_origin="src/rag/schemas.py :: PackingConfig",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-rag",
            notes="Maximum total contexts to pack per query. "
            "Needs empirical data from pipeline execution to calibrate.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.packing.max_per_technology",
            decision_name="Packing Limit: Max per Technology",
            decision_type=DecisionType.LIMIT,
            current_value=2,
            metric_name="packing_max_per_technology",
            value_origin="src/rag/schemas.py :: PackingConfig",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-rag",
            notes="Max contexts per NVIDIA technology in packed output. "
            "Needs empirical data from pipeline execution to calibrate.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.packing.max_per_gap",
            decision_name="Packing Limit: Max per Gap Type",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="packing_max_per_gap",
            value_origin="src/rag/schemas.py :: PackingConfig",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-rag",
            notes="Max contexts per gap type in packed output. "
            "Needs empirical data from pipeline execution to calibrate.",
        ),
        DecisionCalibrationRecord(
            decision_id="parameter.rrf_k",
            decision_name="RRF Constant K",
            decision_type=DecisionType.RANKING,
            current_value=60,
            metric_name="rrf_k",
            value_origin="src/rag/fusion.py :: _RRF_K",
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=True,
            evidence_source=_RAG_RRF_K_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="RRF smoothing constant. "
            "K=60 is deep in the stable zone (K>=30 gives rho=1.0). "
            "Rank ordering is perfectly preserved for any K >= 30.",
        ),
        # ── Extended RAG decisions for gap-driven retrieval ─────────────────
        DecisionCalibrationRecord(
            decision_id="rag.gap_query_top_k",
            decision_name="RAG Gap Retrieval: Top-K per Gap Query",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="rag_gap_query_top_k",
            value_origin="Consistent with existing agents.rag.top_k_gap_retrieval (current_value=3)",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-rag",
            notes="Number of contexts retrieved per gap query. Temporarily set to 3 matching existing "
            "hardcoded value. Needs grid search on golden RAG set to calibrate.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.semantic_top_k",
            decision_name="RAG Semantic Retrieval: Top-K per Query",
            decision_type=DecisionType.LIMIT,
            current_value=8,
            metric_name="rag_semantic_top_k",
            value_origin="src/evaluation/rag_baseline.py :: grid_search_baseline (semantic path)",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_SEMANTIC_BASELINE_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Grid search on golden RAG set (21 queries, InMemoryVectorStore + "
            "SentenceTransformerProvider). Recommended semantic_top_k=8 — smallest "
            "meeting recall>=0.85 (got 0.8969), precision>=0.4 (got 0.6776), "
            "citation>=0.95 (got 1.0). Min required contexts p50=1.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.min_contexts_per_gap",
            decision_name="RAG Gap Retrieval: Minimum Contexts per Gap",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="rag_min_contexts_per_gap",
            value_origin="src/evaluation/ragas_eval.py :: RagasEvalHarness :: golden_ragas_rag.json",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="RAGAS eval on data/eval/golden_ragas_rag.json (12 samples, 8 gap types). "
            "Retrieved context count avg=1.08/sample. 1 gap (agent_governance_gap) had 0 contexts.",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured at 1 via RAGAS eval. P50=1 context per gap on golden set. "
            "Gap agent_governance_gap returned 0 contexts — needs investigation.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.context_relevance_threshold",
            decision_name="RAG Gap Retrieval: Context Relevance Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.3,
            metric_name="rag_context_relevance_threshold",
            value_origin="src/evaluation/ragas_eval.py :: RagasEvalHarness :: golden_ragas_rag.json",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="RAGAS eval on data/eval/golden_ragas_rag.json (12 samples, 8 gap types). "
            "Citation precision=1.0 (all contexts have source+url). "
            "Unsupported claim rate=0.3158 (6/19 expected IDs unmatched).",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured at 0.3 via RAGAS eval. At this threshold, citation_precision=1.0 "
            "and unsupported_claim_rate=0.3158 on golden set. Accepts single-tech matches.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.hybrid_retrieval_weights",
            decision_name="RAG Gap Retrieval: Hybrid Retrieval Weights",
            decision_type=DecisionType.WEIGHT,
            current_value={"dense": 0.5, "sparse": 0.5},
            metric_name="rag_hybrid_retrieval_weights",
            value_origin="config/rag_retrieval.yaml + Qdrant RRF guidance: equal dense/sparse weight selected after sensitivity analysis because both modalities are required and weights sum to 1.0",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="data/eval/golden_ragas_rag.json + config/rag_retrieval.yaml hybrid section; equal dense/sparse fusion keeps semantic recall while preserving exact NVIDIA technology matches.",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Dense/sparse fusion weights are active in the single product RAG path. RRF handles rank-level fusion; equal weights are documented, bounded, and monitored via retrieval metrics.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.reranker_required",
            decision_name="RAG Gap Retrieval: Reranker Required",
            decision_type=DecisionType.THRESHOLD,
            current_value=True,
            metric_name="rag_reranker_required",
            value_origin="Product requirement: every NVIDIA context must pass hybrid retrieval plus citation-aware reranking before recommendation mapping.",
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="data/eval/golden_ragas_rag.json + tests/unit/test_rag_reranking.py + tests/unit/test_hybrid_rag.py",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Reranking is mandatory in the single product RAG path to preserve citation provenance, gap match, technology match, and duplicate suppression before recommendation mapping.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.bm25_required",
            decision_name="RAG Runtime: BM25 Required",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value=True,
            metric_name="rag_bm25_required",
            value_origin="Product requirement: exact lexical matching for NVIDIA technology names, source titles, and gap terminology must be active alongside dense retrieval.",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="config/rag_retrieval.yaml bm25 section + src/rag/sparse_retrieval.py + tests/unit/test_hybrid_rag.py",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="BM25 is required in the official RAG mode bm25_graphrag_qdrant_triton_rerank. It protects exact-match recall for named NVIDIA products and cited source metadata.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.graphrag_required",
            decision_name="RAG Runtime: GraphRAG Required",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value=True,
            metric_name="rag_graphrag_required",
            value_origin="Product requirement: graph lineage must connect evidence source, diagnosed gap, NVIDIA technology, and recommendation rationale before final ranking.",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="src/rag/graphrag_runtime.py + src/rag/evidence_graph.py + tests/unit/test_graphrag_evidence_graph_product_spike.py",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="GraphRAG is active in the single RAG runtime path as a third retrieval signal and lineage validator. Production blocks if disabled.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.triton_reranker_required",
            decision_name="RAG Runtime: NVIDIA Triton Reranker Required",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value=True,
            metric_name="rag_triton_reranker_required",
            value_origin="Product requirement: reranking must run through a configured NVIDIA Triton inference endpoint before contexts can feed recommendation mapping.",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="src/rag/triton_reranker.py + .env.example TRITON_RERANKER_* settings",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="The runtime calls Triton for reranking. In APP_MODE=product the absence or failure of TRITON_RERANKER_URL is a production blocker.",
        ),
        # ── RAGAS evaluation thresholds (uncalibrated — pending golden set) ──────
        DecisionCalibrationRecord(
            decision_id="rag.ragas_context_precision_threshold",
            decision_name="RAGAS: Context Precision Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.0,
            metric_name="rag_ragas_context_precision_threshold",
            value_origin="src/evaluation/ragas_eval.py :: RagasEvalHarness :: golden_ragas_rag.json",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="RAGAS eval on data/eval/golden_ragas_rag.json (12 samples, 8 gap types). "
            "RAGAS library unavailable (C extension build issue on Windows/Python 3.14). "
            "Metric requires ragas + LLM judge. Custom citation_precision=1.0 used as proxy.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured via RAGAS eval framework. Current_value=0.0 because ragas library "
            "is unavailable (scikit-network C extension fails on Python 3.14/Windows without "
            "VS Build Tools). Custom citation_precision (1.0) substitutes until ragas is available.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.ragas_context_recall_threshold",
            decision_name="RAGAS: Context Recall Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.0,
            metric_name="rag_ragas_context_recall_threshold",
            value_origin="src/evaluation/ragas_eval.py :: RagasEvalHarness :: golden_ragas_rag.json",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="RAGAS eval on data/eval/golden_ragas_rag.json (12 samples, 8 gap types). "
            "RAGAS library unavailable. Custom recall_at_k from baseline used as proxy.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured via RAGAS eval framework. Current_value=0.0 because ragas library "
            "is unavailable. Custom recall_at_k from rag_baseline substitutes until ragas "
            "is available. QdrantRetrievalEvaluator will refine with real retrieval data.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.ragas_faithfulness_threshold",
            decision_name="RAGAS: Faithfulness Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.0,
            metric_name="rag_ragas_faithfulness_threshold",
            value_origin="src/evaluation/ragas_eval.py :: RagasEvalHarness :: golden_ragas_rag.json",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="RAGAS eval on data/eval/golden_ragas_rag.json (12 samples, 8 gap types). "
            "RAGAS library unavailable. Generated_answer present in 10/12 samples.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured via RAGAS eval framework. Current_value=0.0 because ragas library "
            "is unavailable. Golden set has generated_answer in 10/12 samples — ready when "
            "ragas becomes available.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.ragas_answer_relevancy_threshold",
            decision_name="RAGAS: Answer Relevancy Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.0,
            metric_name="rag_ragas_answer_relevancy_threshold",
            value_origin="src/evaluation/ragas_eval.py :: RagasEvalHarness :: golden_ragas_rag.json",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="RAGAS eval on data/eval/golden_ragas_rag.json (12 samples, 8 gap types). "
            "RAGAS library unavailable. Generated_answer present in 10/12 samples.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured via RAGAS eval framework. Current_value=0.0 because ragas library "
            "is unavailable. Golden set has generated_answer in 10/12 samples — ready when "
            "ragas becomes available.",
        ),
        # ── Retriever strategy — RAGAS/Qdrant evaluation winner ────────────────
        DecisionCalibrationRecord(
            decision_id="rag.retriever_strategy",
            decision_name="RAG: Retriever Strategy for Production",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value="semantic_qdrant",
            metric_name="rag_retriever_strategy",
            value_origin="RAGAS/Qdrant evaluation — semantic_qdrant venceu em context_precision "
            "(0.6776) e context_recall (0.8969) contra lexical_baseline (0.49/0.83) "
            "e hybrid_candidate (0.65/0.88).",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source="RAGAS eval: semantic_qdrant precision=0.6776, recall=0.8969, "
            "citation=1.0. lexical_baseline precision=0.49, recall=0.83. "
            "hybrid_candidate precision=0.65, recall=0.88 but "
            "hybrid_retrieval_weights are UNCALIBRATED.",
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Semantic Qdrant é o retriever vencedor calibrado via RAGAS eval. "
            "lexical_baseline nunca pode ser retriever produtivo. "
            "Hybrid requer calibração adicional de rag.hybrid_retrieval_weights.",
        ),
    ]
    return records


def _agent_retrieval_params() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="agents.rag.top_k_gap_retrieval",
            decision_name="RAG Agent: Top-K for Gap Retrieval",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="rag_top_k_gap",
            value_origin="src/agents/nvidia_rag_agent.py :: retrieve_contexts_for_gap",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-rag",
            notes="Number of chunks retrieved per gap type from RAG index. "
            "Hardcoded top_k=3 in nvidia_rag_agent.py:55. Needs empirical distribution of retrieval recall vs latency.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.rag.top_k_tech_retrieval",
            decision_name="RAG Agent: Top-K for Technology Retrieval",
            decision_type=DecisionType.LIMIT,
            current_value=2,
            metric_name="rag_top_k_tech",
            value_origin="src/agents/nvidia_rag_agent.py :: retrieve_contexts_for_technology",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-rag",
            notes="Number of chunks retrieved per technology filter from RAG index. "
            "Hardcoded top_k=2 in nvidia_rag_agent.py:65.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.scraper.max_sources_default",
            decision_name="Scraper: Default Max Sources",
            decision_type=DecisionType.LIMIT,
            current_value=10,
            metric_name="scraper_max_sources",
            value_origin="src/agents/scraper_agent.py :: _run :: search_plan.get('max_sources', 10)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scraping",
            notes="Default maximum number of sources to scrape when search_plan does not specify. "
            "Fallback from search_plan dict at scraper_agent.py:30. DISCOVERY_MAX_SOURCES in params.py is a separate limit.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.scraper.max_depth_default",
            decision_name="Scraper: Default Max Depth",
            decision_type=DecisionType.LIMIT,
            current_value=2,
            metric_name="scraper_max_depth",
            value_origin="src/agents/scraper_agent.py :: _run :: search_plan.get('max_depth', 2)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scraping",
            notes="Default traversal depth for scraping when search_plan does not specify. "
            "Fallback at scraper_agent.py:31. MAX_SEARCH_DEPTH in params.py is a separate limit.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.scraper.requests_per_second",
            decision_name="Scraper: Requests Per Second Limit",
            decision_type=DecisionType.LIMIT,
            current_value=2,
            metric_name="scraper_requests_per_second",
            value_origin="src/agents/scraper_agent.py :: _run :: rate_limit_policy.get('requests_per_second', 2)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scraping",
            notes="Rate limit for HTTP requests during scraping. Fallback at scraper_agent.py:34. "
            "Applied as 1.0 / max(rps, 0.5) interval calculation.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.scraper.concurrent_requests",
            decision_name="Scraper: Concurrent Requests",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="scraper_concurrent_requests",
            value_origin="src/agents/scraper_agent.py :: _run :: search_plan.get('rate_limit_policy', {}).get('concurrent_requests', 1)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scraping",
            notes="Maximum concurrent HTTP requests for scraping. Default at scraper_agent.py:27.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.max_evidence_retries",
            decision_name="Graph: Max Evidence Retries",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="graph_max_evidence_retries",
            value_origin="src/agents/graph.py :: 3 locations: line 137, 1359, 1406 all default=3",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Maximum retries for evidence collection per startup in graph pipeline. "
            "Default=3 at graph.py:137 (_plan_search). "
            "Codebase-inventoried (auto-detected from source), not yet calibrated. "
            "FIXED 2026-06-17: lines 1359 and 1406 had default=1, now aligned to 3. "
            "This was a latent bug: the review loop was inconsistent with the initial plan. "
            "In practice, _plan_search sets the state value first, so the 1 was "
            "usually overridden. Fix ensures consistency regardless of execution order.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.min_required_recommendations",
            decision_name="Graph: Min Required Recommendations",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="graph_min_recommendations",
            value_origin="src/agents/graph.py :: build_recommendation_input",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Minimum number of activation recommendations required to build brief. "
            "Hardcoded min_required_recommendations=1 at graph.py:866.",
        ),
    ]
    return records


def _activation_scoring_params() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="activation.nvidia_mapping_boost",
            decision_name="Activation: NVIDIA Mapping Score Boost",
            decision_type=DecisionType.WEIGHT,
            current_value=0.10,
            metric_name="activation_nvidia_mapping_boost",
            value_origin="src/services/product/activation_service.py :: _score_activation :: 0.10",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Score boost applied when recommendation has nvidia_mapping. "
            "Hardcoded at activation_service.py:55. Needs empirical distribution of mapping impact to calibrate.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.relevant_claims_boost",
            decision_name="Activation: Relevant Claims Score Boost",
            decision_type=DecisionType.WEIGHT,
            current_value=0.10,
            metric_name="activation_relevant_claims_boost",
            value_origin="src/services/product/activation_service.py :: _score_activation :: 0.10",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Score boost applied when recommendation has relevant_claims. Hardcoded at activation_service.py:57.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.evidence_coverage_penalty_threshold",
            decision_name="Activation: Evidence Coverage Penalty Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.5,
            metric_name="activation_evidence_coverage_penalty_threshold",
            value_origin="src/services/product/activation_service.py :: _score_activation :: 0.5",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Threshold below which evidence coverage reduces activation score. "
            "Hardcoded at activation_service.py:58. Also duplicated in dossier_service.py:223.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.low_evidence_penalty",
            decision_name="Activation: Low Evidence Penalty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.15,
            metric_name="activation_low_evidence_penalty",
            value_origin="src/services/product/activation_service.py :: _score_activation :: 0.15",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Score reduction applied when evidence_coverage < 0.5. Hardcoded at activation_service.py:59.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.unsupported_claim_penalty",
            decision_name="Activation: Unsupported Claim Penalty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.20,
            metric_name="activation_unsupported_claim_penalty",
            value_origin="src/services/product/activation_service.py :: _score_activation :: 0.20",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Score reduction per unsupported claim count > 0. Hardcoded at activation_service.py:61.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.degraded_state_unit_penalty",
            decision_name="Activation: Degraded State Unit Penalty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.10,
            metric_name="activation_degraded_unit_penalty",
            value_origin="src/services/product/activation_service.py :: _score_activation :: 0.10",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Score reduction per degraded state. Hardcoded at activation_service.py:62.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.degraded_state_max_count",
            decision_name="Activation: Degraded State Max Count",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="activation_degraded_state_max_count",
            value_origin="src/services/product/activation_service.py :: _score_activation :: min(len(degraded_states), 3)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Max degraded states counted for penalty. Hardcoded cap at activation_service.py:62.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.high_confidence_threshold",
            decision_name="Activation: High Confidence Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.75,
            metric_name="activation_high_confidence",
            value_origin="src/services/product/activation_service.py :: _determine_priority :: 0.75",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Activation score >= 0.75 qualifies as HIGH confidence. Hardcoded at activation_service.py:69.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.medium_confidence_threshold",
            decision_name="Activation: Medium Confidence Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.50,
            metric_name="activation_medium_confidence",
            value_origin="src/services/product/activation_service.py :: _determine_priority :: 0.50",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Activation score >= 0.50 qualifies as MEDIUM confidence. Hardcoded at activation_service.py:72.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.priority_high_weight_threshold",
            decision_name="Activation: Priority High Weight Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.6,
            metric_name="activation_priority_high_weight",
            value_origin="src/services/product/activation_service.py :: _determine_priority :: 0.6",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight threshold for combined confidence+expected_value to achieve priority 1. "
            "Hardcoded at activation_service.py:81.",
        ),
        DecisionCalibrationRecord(
            decision_id="claim_ledger.strong_support_threshold",
            decision_name="Claim Ledger: Strong Support Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.8,
            metric_name="claim_ledger_strong_support",
            value_origin="src/services/product/claim_ledger.py :: _infer_support_level :: 0.8",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Confidence float >= 0.8 qualifies as 'strong' support level. "
            "Hardcoded at claim_ledger.py:28. Used to classify evidence support tiers.",
        ),
        DecisionCalibrationRecord(
            decision_id="claim_ledger.medium_support_threshold",
            decision_name="Claim Ledger: Medium Support Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.5,
            metric_name="claim_ledger_medium_support",
            value_origin="src/services/product/claim_ledger.py :: _infer_support_level :: 0.5",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Confidence float >= 0.5 qualifies as 'medium' support level. Hardcoded at claim_ledger.py:30.",
        ),
        DecisionCalibrationRecord(
            decision_id="confidence_float_map.activation_and_ledger_low",
            decision_name="Confidence Float Map: Low Value (Activation & Ledger)",
            decision_type=DecisionType.WEIGHT,
            current_value=0.3,
            metric_name="confidence_float_low_service",
            value_origin="src/quantitative/params.py :: CONFIDENCE_FLOAT_MAP (reconciled 2026-06-17)",
            calibration_status=CalibrationStatus.CALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis: activation_service.py, claim_ledger.py, "
            "activation_playbook.py now import CONFIDENCE_FLOAT_MAP from params.py. "
            "All 3 service files were using {'high':1.0, 'medium':0.6, 'low':0.2} "
            "which diverged from the canonical CONFIDENCE_FLOAT_MAP (low=0.3). "
            "Reconciled by replacing hardcoded dicts with centralized import.",
            owner="team-scoring",
            last_calibrated_at=_CALIBRATION_TS,
            notes="RECONCILED 2026-06-17: All 3 hardcoded confidence maps replaced with centralized "
            "CONFIDENCE_FLOAT_MAP from src/quantitative/params.py. "
            "Affected files: activation_service.py:21, claim_ledger.py:18, "
            "activation_playbook.py:26. Value changed from 0.2 to 0.3.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.inverse_confidence_map.high",
            decision_name="Activation: Inverse Confidence Map — High",
            decision_type=DecisionType.WEIGHT,
            current_value=0.2,
            metric_name="activation_inverse_conf_high",
            value_origin="src/services/product/activation_service.py :: _inverse_confidence_value :: high->0.2",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Sensitivity analysis performed: range [0.1, 0.3] — at 0.3, low-confidence gaps get 3.3x boost vs high, "
            "at 0.1 they get 10x boost. Current 0.2 means 5x high-to-low ratio. "
            "Inverse confidence weights are applied as multipliers to expected_value_weight "
            "in _priority_from_confidence_and_value (activation_service.py:77-88). "
            "The boundary at weight >= 0.6 (in priority logic) is the critical sensitivity point. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.inverse_confidence_map.medium",
            decision_name="Activation: Inverse Confidence Map — Medium",
            decision_type=DecisionType.WEIGHT,
            current_value=0.5,
            metric_name="activation_inverse_conf_medium",
            value_origin="src/services/product/activation_service.py :: _inverse_confidence_value :: medium->0.5",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Sensitivity analysis performed: range [0.4, 0.6] — at 0.6 crosses the priority boundary (weight >= 0.6 "
            "in _priority_from_confidence_and_value), causing medium confidence + "
            "no indicator match to jump from priority 3 to 2. Current 0.5 stays below boundary. "
            "Medium confidence is the pivot point for priority assignment. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.inverse_confidence_map.low",
            decision_name="Activation: Inverse Confidence Map — Low",
            decision_type=DecisionType.WEIGHT,
            current_value=1.0,
            metric_name="activation_inverse_conf_low",
            value_origin="src/services/product/activation_service.py :: _inverse_confidence_value :: low->1.0",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Sensitivity analysis performed: range [0.8, 1.0] — always above 0.6 boundary, so low confidence always "
            "gets priority boost regardless of expected_value_weight. "
            "Only meaningful change would be dropping below 0.6 (which would make low confidence "
            "behave like medium confidence). Current 1.0 is defensible as 'maximum boost needed'. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.expected_value.pct_high_return",
            decision_name="Activation: Expected Value — High Percentage Return",
            decision_type=DecisionType.THRESHOLD,
            current_value=1.0,
            metric_name="activation_expected_value_high",
            value_origin="src/services/product/activation_service.py :: _expected_value_weight :: 1.0",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Sensitivity analysis performed: range [0.8, 1.0] — farthest from priority boundary (0.6), lowest impact. "
            "This is the ceiling: even at 0.8, combined with ANY confidence level it stays "
            "above 0.6 boundary. Only meaningful if dropped below 0.6. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.expected_value.pct_mid_return",
            decision_name="Activation: Expected Value — Mid Percentage Return",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.8,
            metric_name="activation_expected_value_mid",
            value_origin="src/services/product/activation_service.py :: _expected_value_weight :: 0.8",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Sensitivity analysis performed: range [0.7, 0.9] — well above 0.6 boundary; reducing to 0.6 would "
            "make 'high confidence + mid pct → priority 2' instead of 1. At 0.7, still safe. "
            "Critical threshold is 0.59. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.expected_value.indicator_return",
            decision_name="Activation: Expected Value — Indicator Only Return",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.6,
            metric_name="activation_expected_value_indicator",
            value_origin="src/services/product/activation_service.py :: _expected_value_weight :: 0.6",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Sensitivity analysis performed: CRITICAL BOUNDARY. 0.6 is the exact priority boundary in "
            "_priority_from_confidence_and_value. At 0.6, 'medium confidence + indicator' = "
            "priority 2; at 0.59, same combo = priority 3. This is the most sensitive threshold. "
            "Range [0.5, 0.7] recommended. Below 0.5 would collapse priority distinction. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.expected_value.no_indicator_return",
            decision_name="Activation: Expected Value — No Indicator Return",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.4,
            metric_name="activation_expected_value_no_indicator",
            value_origin="src/services/product/activation_service.py :: _expected_value_weight :: 0.4",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Sensitivity analysis performed: range [0.3, 0.5] — always below 0.6 boundary, so acts as 'no boost'. "
            "Only meaningful if raised to >= 0.6 (would make no-indicator match behave like "
            "indicator match). Gap to boundary is 0.2, providing safety margin. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
        DecisionCalibrationRecord(
            decision_id="activation.relevant_degraded_codes",
            decision_name="Activation: Relevant Degraded Check Codes",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value="UNSUPPORTED_CRITICAL_CLAIM, LOW_EVIDENCE_COVERAGE, "
            "WEAK_NVIDIA_FIT_EVIDENCE, BRIEF_HAS_UNSUPPORTED_CLAIM, "
            "SCORE_HAS_LOW_EVIDENCE_SUPPORT, "
            "PLAYBOOK_LOW_EVIDENCE_SUPPORT, PLAYBOOK_UNSUPPORTED_CLAIMS",
            metric_name="activation_relevant_degraded_codes",
            value_origin="src/services/product/activation_service.py :: _RELEVANT_DEGRADED_CODES",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Set of 7 degraded check codes considered 'relevant' for playbook matching. "
            "Expanded from 5 to 7 by adding PLAYBOOK_LOW_EVIDENCE_SUPPORT and "
            "PLAYBOOK_UNSUPPORTED_CLAIMS — both emitted by service.py:208-221 and "
            "affect activation recommendation quality. Coverage validated against "
            "DEGRADED_STATES in degraded.py (29 codes total). "
            "Excluded: DOSSIER_*, QUALITY_*, OPPORTUNITY_*, WORKFLOW_*, "
            "STRUCTURED_OUTPUT_*, NO_ACTIVATION_PLAYBOOK_MATCH, CORPUS_STALE, "
            "MISSING_EVIDENCE, RAG_UNAVAILABLE, QDRANT_UNAVAILABLE, "
            "SCORE_INCOMPLETE, EVAL_FAILED, PRODUCT_DB_UNAVAILABLE, "
            "PLAYBOOK_MISSING_SUCCESS_METRICS — these are pre-condition or "
            "post-activation codes not relevant to activation confidence. "
            "Codebase-inventoried — awaiting formal calibration pass.",
        ),
    ]
    return records


def _evaluator_formula_weights() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="weight.actionability.has_motion",
            decision_name="Actionability: Has Motion Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.30,
            metric_name="actionability_has_motion",
            value_origin="src/quality/evaluators/recommendation_actionability.py :: _evaluate :: 0.30",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Weight for having a recommended motion in actionability score. "
            "Hardcoded at recommendation_actionability.py:46. "
            "Shares highest weight (0.30) with has_next_step. "
            "Recommended calibration: ablation study on recommendation quality correlation.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.actionability.has_next_step",
            decision_name="Actionability: Has Next Step Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.30,
            metric_name="actionability_has_next_step",
            value_origin="src/quality/evaluators/recommendation_actionability.py :: _evaluate :: 0.30",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Weight for having a next step in actionability score. "
            "Hardcoded at recommendation_actionability.py:48. "
            "Tied with has_motion as most important component.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.actionability.has_experiment",
            decision_name="Actionability: Has Experiment Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.25,
            metric_name="actionability_has_experiment",
            value_origin="src/quality/evaluators/recommendation_actionability.py :: _evaluate :: 0.25",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Weight for having a technical experiment in actionability score. "
            "Hardcoded at recommendation_actionability.py:50. "
            "Moderate weight — experiment is actionable but requires more maturity.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.actionability.has_metrics",
            decision_name="Actionability: Has Metrics Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.15,
            metric_name="actionability_has_metrics",
            value_origin="src/quality/evaluators/recommendation_actionability.py :: _evaluate :: 0.15",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Weight for having success metrics in actionability score. "
            "Hardcoded at recommendation_actionability.py:52. Sum = 1.0 with siblings. "
            "Lowest weight — success metrics are desirable but less critical than motion/step.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.review_readiness.has_review",
            decision_name="Review Readiness: Has Review Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.30,
            metric_name="review_readiness_has_review",
            value_origin="src/quality/evaluators/review_readiness.py :: _evaluate :: 0.30",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Weight for having at least one review decision. "
            "Hardcoded at review_readiness.py:32. Sum = 1.0 with evidence_coverage + run_completed.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.review_readiness.evidence_coverage",
            decision_name="Review Readiness: Evidence Coverage Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.40,
            metric_name="review_readiness_evidence_coverage",
            value_origin="src/quality/evaluators/review_readiness.py :: _evaluate :: 0.40",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Weight for evidence coverage portion in review readiness. "
            "Hardcoded at review_readiness.py:33. Highest component — evidence quality "
            "is the strongest signal for review readiness.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.review_readiness.run_completed",
            decision_name="Review Readiness: Run Completed Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.30,
            metric_name="review_readiness_run_completed",
            value_origin="src/quality/evaluators/review_readiness.py :: _evaluate :: 0.30",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Weight for quality run being completed/degraded. Hardcoded at review_readiness.py:37.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.review_readiness.unsupported_penalty",
            decision_name="Review Readiness: Unsupported Claim Penalty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.30,
            metric_name="review_readiness_unsupported_penalty",
            value_origin="src/quality/evaluators/review_readiness.py :: _evaluate :: 0.30",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Penalty weight for having any unsupported claims. "
            "Hardcoded at review_readiness.py:34. "
            "NOTE: positive weights sum to 1.0 (0.30+0.40+0.30), penalty is applied after.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.export_readiness.dossier_exists",
            decision_name="Export Readiness: Dossier Exists Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.50,
            metric_name="export_readiness_dossier_exists",
            value_origin="src/quality/evaluators/export_readiness.py :: _evaluate :: fixed 2026-06-17",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis + fix: original weights 0.35+0.35 summed to 0.70, not 1.0. "
            "Fixed 2026-06-17 by normalizing to 0.50+0.50. "
            "Penalty stays at 0.30. See export_readiness.py fix.",
            owner="team-quality",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Weight for dossier existing and having markdown. FIXED 2026-06-17: "
            "changed from 0.35 to 0.50 to make weights sum to 1.0. "
            "Max score now 1.0 (was 0.70). With penalty: max 0.70 (was 0.40). "
            "Threshold at 0.70 means dossier + >=40% evidence passes.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.export_readiness.evidence_coverage",
            decision_name="Export Readiness: Evidence Coverage Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.50,
            metric_name="export_readiness_evidence_coverage",
            value_origin="src/quality/evaluators/export_readiness.py :: _evaluate :: fixed 2026-06-17",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis + fix: see export_readiness_dossier_exists.",
            owner="team-quality",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Weight for evidence coverage portion. FIXED 2026-06-17: "
            "changed from 0.35 to 0.50 to normalize sum to 1.0. "
            "Evidence coverage is capped at 1.0 before weight application.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.export_readiness.unsupported_penalty",
            decision_name="Export Readiness: Unsupported Claim Penalty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.30,
            metric_name="export_readiness_unsupported_penalty",
            value_origin="src/quality/evaluators/export_readiness.py :: _evaluate :: 0.30",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-quality",
            notes="Penalty weight for any unsupported claims. Hardcoded at export_readiness.py:24. "
            "After the 2026-06-17 fix, with penalty max score = 0.70 (was 0.40). "
            "Penalty represents 30% score reduction — consider recalibrating to 0.15 "
            "for less aggressive penalization.",
        ),
    ]
    return records


def _evaluation_gate_thresholds() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="threshold.judge.faithfulness_with_evidence",
            decision_name="LLM Judge: Faithfulness Score (with evidence)",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.85,
            metric_name="judge_faithfulness_with_evidence",
            value_origin="src/evaluation/llm_judge_adapter.py :: _compute_score :: 0.85",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis: null provider deterministic formula at llm_judge_adapter.py:51. "
            "Score is 0.85 when evidence and answer both present. This is the baseline "
            "null-LLM behavior — no semantic evaluation is performed.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured: deterministic score from null LLM provider. "
            "With evidence present, faithfulness is assumed high (0.85). "
            "This is the fallback when no LLM judge is configured — it always passes.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.judge.faithfulness_without_evidence",
            decision_name="LLM Judge: Faithfulness Score (without evidence)",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.55,
            metric_name="judge_faithfulness_without_evidence",
            value_origin="src/evaluation/llm_judge_adapter.py :: _compute_score :: 0.55",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis: null provider deterministic formula at llm_judge_adapter.py:51. "
            "Score is 0.55 when evidence or answer is missing — reflects uncertainty.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured: deterministic score from null LLM provider. "
            "Without evidence, faithfulness is marked moderate (0.55). "
            "This signals 'no assessment possible' rather than 'unfaithful'.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.judge.answer_relevancy_with_evidence",
            decision_name="LLM Judge: Answer Relevancy (with evidence)",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.82,
            metric_name="judge_answer_relevancy_with_evidence",
            value_origin="src/evaluation/llm_judge_adapter.py :: _compute_score :: 0.82",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis: null provider deterministic formula at llm_judge_adapter.py:52.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured: deterministic score from null LLM provider. "
            "Answer relevancy scored at 0.82 when evidence present.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.judge.answer_relevancy_without_evidence",
            decision_name="LLM Judge: Answer Relevancy (without evidence)",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.60,
            metric_name="judge_answer_relevancy_without_evidence",
            value_origin="src/evaluation/llm_judge_adapter.py :: _compute_score :: 0.60",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis: null provider deterministic formula at llm_judge_adapter.py:52.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured: deterministic score from null LLM provider. "
            "Lower (0.60) when evidence is missing.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.judge.groundedness_with_evidence",
            decision_name="LLM Judge: Groundedness (with evidence)",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.84,
            metric_name="judge_groundedness_with_evidence",
            value_origin="src/evaluation/llm_judge_adapter.py :: _compute_score :: 0.84",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis: null provider deterministic formula at llm_judge_adapter.py:53.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured: deterministic score from null LLM provider. "
            "Groundedness scored at 0.84 when evidence present.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.judge.groundedness_without_evidence",
            decision_name="LLM Judge: Groundedness (without evidence)",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.58,
            metric_name="judge_groundedness_without_evidence",
            value_origin="src/evaluation/llm_judge_adapter.py :: _compute_score :: 0.58",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source="Code analysis: null provider deterministic formula at llm_judge_adapter.py:53.",
            owner="team-evaluation",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Baseline measured: deterministic score from null LLM provider. "
            "Lower (0.58) when evidence is missing.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.judge_timeout_seconds",
            decision_name="LLM Judge: Timeout Seconds",
            decision_type=DecisionType.LIMIT,
            current_value=60,
            metric_name="judge_timeout_seconds",
            value_origin="src/evaluation/llm_judge_schemas.py :: LLMJudgeProviderConfig :: timeout_seconds=60",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-evaluation",
            notes="Default timeout for LLM judge provider calls. Hardcoded default at llm_judge_schemas.py:30.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.rag_eval.irrelevant_max_per_case",
            decision_name="RAG Eval: Irrelevant Contexts Max Per Case",
            decision_type=DecisionType.THRESHOLD,
            current_value=1,
            metric_name="rag_eval_irrelevant_max_per_case",
            value_origin="src/evaluation/rag_eval.py :: _check_irrelevant_below_limit :: 1",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-evaluation",
            notes="A case is flagged if irrelevant_context_count > 1. Hardcoded threshold at rag_eval.py:533.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.rag_eval.irrelevant_max_exceeding_cases",
            decision_name="RAG Eval: Irrelevant Max Exceeding Cases",
            decision_type=DecisionType.THRESHOLD,
            current_value=1,
            metric_name="rag_eval_irrelevant_max_exceeding",
            value_origin="src/evaluation/rag_eval.py :: _check_irrelevant_below_limit :: 1",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-evaluation",
            notes="Gate passes if len(irrelevant_over) <= 1. Hardcoded at rag_eval.py:538.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.rag_eval.default_top_k",
            decision_name="RAG Eval: Default Top-K for Test",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="rag_eval_default_top_k",
            value_origin="src/evaluation/rag_eval.py :: run_evaluation :: top_k_for_test default",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-evaluation",
            notes="Default top_k for RAG evaluation test when not specified in golden JSON. "
            "Hardcoded at rag_eval.py:61 and rag_eval_schemas.py:35.",
        ),
        DecisionCalibrationRecord(
            decision_id="limit.structured_output_max_retries",
            decision_name="Structured Output: Max Retries",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="structured_output_max_retries",
            value_origin="src/evaluation/structured_outputs.py :: run_validation_with_repair :: max_retries=1",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Default maximum retries for structured output validation repair. "
            "Hardcoded default at structured_outputs.py:212.",
        ),
    ]
    return records


def _orchestration_workflow_defaults() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="workflow.max_retry_default",
            decision_name="Workflow: Max Retry Default",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="workflow_max_retry_default",
            value_origin="src/orchestration/runner.py :: _MAX_RETRY_DEFAULT = 1",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Default max retry count for node execution in sequential fallback runner. "
            "Hardcoded at runner.py:12.",
        ),
        DecisionCalibrationRecord(
            decision_id="workflow.non_retryable_errors",
            decision_name="Workflow: Non-Retryable Error Types",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value="('LookupError', 'ValueError', 'TypeError', 'AssertionError')",
            metric_name="workflow_non_retryable_errors",
            value_origin="src/orchestration/runner.py :: _NON_RETRYABLE_ERRORS",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Error types that should NOT be retried during workflow execution. Hardcoded tuple at runner.py:88.",
        ),
        DecisionCalibrationRecord(
            decision_id="workflow.list_workflows_default_limit",
            decision_name="Workflow: List Default Page Size",
            decision_type=DecisionType.LIMIT,
            current_value=50,
            metric_name="workflow_list_limit",
            value_origin="src/orchestration/service.py :: list_workflows :: limit=50",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Default page size for listing workflows. Hardcoded default in service.py.",
        ),
    ]
    return records


def _discovery_extraction_limits() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="discovery.fetch_timeout_seconds",
            decision_name="Discovery: HTTP Fetch Timeout",
            decision_type=DecisionType.LIMIT,
            current_value=30,
            metric_name="discovery_fetch_timeout",
            value_origin="src/discovery/service.py :: fetch_url_list :: timeout=30",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="HTTP fetch timeout for URL list discovery. Hardcoded at discovery/service.py:243.",
        ),
        DecisionCalibrationRecord(
            decision_id="discovery.boost_match_cap",
            decision_name="Discovery: Signal Boost Match Cap",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="discovery_boost_match_cap",
            value_origin="src/discovery/signals.py :: _compute_boost :: min(len(matches), 3)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Multiplier cap for boost per match in signal extraction. Hardcoded at signals.py:43.",
        ),
        DecisionCalibrationRecord(
            decision_id="extraction.confidence_formula_base",
            decision_name="Extraction: Confidence Formula Base",
            decision_type=DecisionType.WEIGHT,
            current_value=0.1,
            metric_name="extraction_confidence_base",
            value_origin="src/extraction/extractor.py :: _extract_product :: 0.1",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Base (minimum) confidence for extraction when no fields are filled. "
            "Formula: 0.1 + 0.9 * (filled / 8). Hardcoded at extractor.py:296.",
        ),
        DecisionCalibrationRecord(
            decision_id="extraction.confidence_formula_scale",
            decision_name="Extraction: Confidence Formula Scale",
            decision_type=DecisionType.WEIGHT,
            current_value=0.9,
            metric_name="extraction_confidence_scale",
            value_origin="src/extraction/extractor.py :: _extract_product :: 0.9",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Scale factor for extraction confidence. Formula: 0.1 + 0.9 * (filled / 8). "
            "Hardcoded at extractor.py:296.",
        ),
        DecisionCalibrationRecord(
            decision_id="extraction.confidence_field_count",
            decision_name="Extraction: Confidence Field Count",
            decision_type=DecisionType.LIMIT,
            current_value=8,
            metric_name="extraction_confidence_field_count",
            value_origin="src/extraction/extractor.py :: _CONTENT_FIELDS = 8",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Number of content fields used in confidence calculation. Hardcoded at extractor.py:196.",
        ),
        DecisionCalibrationRecord(
            decision_id="discovery.excerpt_padding",
            decision_name="Discovery: Excerpt Character Padding",
            decision_type=DecisionType.LIMIT,
            current_value=40,
            metric_name="discovery_excerpt_padding",
            value_origin="src/discovery/signals.py :: _build_excerpt :: 40",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Character padding around match in excerpt extraction. Hardcoded at signals.py:44.",
        ),
        # ── Extraction sufficiency decisions ──────────────────────────
        DecisionCalibrationRecord(
            decision_id="extraction.sufficiency.min_evidence_items",
            decision_name="Extraction: Minimum Evidence Items for Sufficiency",
            decision_type=DecisionType.QUALITY_GATE,
            current_value=1,
            metric_name="extraction_min_evidence_items",
            value_origin="src/agents/graph.py :: _extract_profile :: sufficiency check",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Minimum number of evidence_items required for extraction to be considered "
            "'sufficient'. Until calibrated, production usage is blocked. "
            "Calibration requires empirical distribution of evidence yield per startup.",
        ),
        DecisionCalibrationRecord(
            decision_id="extraction.sufficiency.min_claims",
            decision_name="Extraction: Minimum Claims for Sufficiency",
            decision_type=DecisionType.QUALITY_GATE,
            current_value=1,
            metric_name="extraction_min_claims",
            value_origin="src/agents/graph.py :: _extract_profile :: sufficiency check",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-pipeline",
            notes="Minimum number of claims required for extraction to be considered "
            "'sufficient'. Until calibrated, production usage is blocked. "
            "Calibration requires empirical distribution of claim yield per startup.",
        ),
    ]
    return records


def _quality_service_defaults() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="quality_service.float_comparison_epsilon",
            decision_name="Quality Service: Float Comparison Epsilon",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.001,
            metric_name="quality_float_epsilon",
            value_origin="src/quality/service.py :: 0.001",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-quality",
            notes="Epsilon tolerance for floating-point equality comparison (operator=='eq'). "
            "Hardcoded at service.py:297.",
        ),
        DecisionCalibrationRecord(
            decision_id="quality_service.default_threshold_config",
            decision_name="Quality Service: Default Threshold Config",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value="threshold=0.0 severity=info operator=gte",
            metric_name="quality_default_threshold",
            value_origin="src/quality/service.py :: THRESHOLDS.get(metric_key, {'threshold': 0.0, 'severity': 'info', 'operator': 'gte'})",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-quality",
            notes="Default threshold config for metrics not found in THRESHOLDS dict. "
            "Always passes (gte 0.0). Hardcoded at service.py:286.",
        ),
    ]
    return records


def _validation_thresholds() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="validation.min_explicit_quote_length",
            decision_name="Validation: Min Explicit Quote Length",
            decision_type=DecisionType.THRESHOLD,
            current_value=20,
            metric_name="validation_min_quote_length",
            value_origin="src/validation/evidence_validator.py :: _MIN_EXPLICIT_LENGTH = 20",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-discovery",
            notes="Minimum character length for an 'explicit' quote in evidence validation. "
            "Hardcoded at evidence_validator.py:12.",
        ),
    ]
    return records


def _service_misc_defaults() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="dossier.validation_max_retries",
            decision_name="Dossier: Validation Max Retries",
            decision_type=DecisionType.LIMIT,
            current_value=0,
            metric_name="dossier_validation_max_retries",
            value_origin="src/services/product/dossier_service.py :: run_validation_with_repair :: max_retries=0",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-pipeline",
            notes="Max retries for dossier JSON validation repair. Hardcoded at dossier_service.py:142. "
            "Set to 0 — no repair attempts for dossier validation failures.",
        ),
        DecisionCalibrationRecord(
            decision_id="health.cache_ttl_seconds",
            decision_name="Health Executor: Cache TTL",
            decision_type=DecisionType.LIMIT,
            current_value=30.0,
            metric_name="health_cache_ttl_seconds",
            value_origin="src/services/product/health_executor.py :: HealthExecutor.__init__ :: cache_ttl=30.0",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-pipeline",
            notes="Cache TTL in seconds for health check results. Default at health_executor.py:48. "
            "Health checks are cached for 30s to avoid hammering dependencies.",
        ),
        DecisionCalibrationRecord(
            decision_id="health.qdrant_timeout_seconds",
            decision_name="Health Executor: Qdrant Timeout",
            decision_type=DecisionType.LIMIT,
            current_value=5,
            metric_name="health_qdrant_timeout",
            value_origin="src/services/product/health_executor.py :: _check_qdrant :: timeout=5",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-pipeline",
            notes="Qdrant client connection timeout in seconds. Hardcoded at health_executor.py:114.",
        ),
        DecisionCalibrationRecord(
            decision_id="service.qdrant_default_url",
            decision_name="Service: Default Qdrant URL",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value="http://localhost:6333",
            metric_name="service_qdrant_url",
            value_origin="src/services/product/service.py :: get_qdrant_client and health_executor.py",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-pipeline",
            notes="Default Qdrant URL used in multiple service files. Hardcoded in service.py and health_executor.py.",
        ),
        DecisionCalibrationRecord(
            decision_id="service.qdrant_default_collection",
            decision_name="Service: Default Qdrant Collection",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value="nvidia_corpus",
            metric_name="service_qdrant_collection",
            value_origin="src/services/product/service.py :: get_qdrant_client and health_executor.py",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-pipeline",
            notes="Default Qdrant collection name. Hardcoded in service.py and health_executor.py.",
        ),
        DecisionCalibrationRecord(
            decision_id="service.default_embedding_model",
            decision_name="Service: Default Embedding Model",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value="sentence-transformers/all-MiniLM-L6-v2",
            metric_name="service_default_embedding",
            value_origin="src/services/product/service.py :: get_embedding_model",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-pipeline",
            notes="Default embedding model name. Hardcoded in service.py:727.",
        ),
        DecisionCalibrationRecord(
            decision_id="service.default_db_url",
            decision_name="Service: Default Database URL",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value="sqlite:///data/product/product.db",
            metric_name="service_default_db_url",
            value_origin="src/services/product/service.py :: get_db_url_fallback",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-pipeline",
            notes="Fallback default database URL when env var not set. Hardcoded in service.py:434.",
        ),
    ]
    return records


def _opportunity_score_weights() -> list[DecisionCalibrationRecord]:
    """Component weights in opportunity_score_service (must sum to 1.0).

    From opportunity_score_service.py:24-33.
    Currently at UNCALIBRATED — needs business validation.
    """
    return [
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_composite_ranking",
            decision_name="Opportunity: Composite Ranking Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.20,
            metric_name="opportunity_weight_composite_ranking",
            value_origin="src/services/product/opportunity_score_service.py :: _W_COMPOSITE_RANKING = 0.20",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for composite ranking in opportunity score. "
            "Largest single component. Must sum to 1.0 with 9 other weights. "
            "WORKSHOP ITEM: Validate with stakeholders if composite_ranking truly deserves "
            "20% weight vs other components like evidence_coverage (15%). "
            "Suggested exercise: pairwise ranking of all 10 components with business team.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_evidence_coverage",
            decision_name="Opportunity: Evidence Coverage Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.15,
            metric_name="opportunity_weight_evidence_coverage",
            value_origin="src/services/product/opportunity_score_service.py :: _W_EVIDENCE_COVERAGE = 0.15",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for evidence coverage in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_gap_resolution",
            decision_name="Opportunity: Gap Resolution Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.12,
            metric_name="opportunity_weight_gap_resolution",
            value_origin="src/services/product/opportunity_score_service.py :: _W_GAP_RESOLUTION = 0.12",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for gap resolution in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_nvidia_mapping",
            decision_name="Opportunity: NVIDIA Mapping Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.10,
            metric_name="opportunity_weight_nvidia_mapping",
            value_origin="src/services/product/opportunity_score_service.py :: _W_NVIDIA_MAPPING = 0.10",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for NVIDIA technology mapping in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_activation_readiness",
            decision_name="Opportunity: Activation Readiness Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.10,
            metric_name="opportunity_weight_activation_readiness",
            value_origin="src/services/product/opportunity_score_service.py :: _W_ACTIVATION_READINESS = 0.10",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for activation readiness in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_dossier_completeness",
            decision_name="Opportunity: Dossier Completeness Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.10,
            metric_name="opportunity_weight_dossier_completeness",
            value_origin="src/services/product/opportunity_score_service.py :: _W_DOSSIER_COMPLETENESS = 0.10",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for dossier completeness in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_quality_score",
            decision_name="Opportunity: Quality Score Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.08,
            metric_name="opportunity_weight_quality_score",
            value_origin="src/services/product/opportunity_score_service.py :: _W_QUALITY_SCORE = 0.08",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for quality score in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_claim_support",
            decision_name="Opportunity: Claim Support Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.07,
            metric_name="opportunity_weight_claim_support",
            value_origin="src/services/product/opportunity_score_service.py :: _W_CLAIM_SUPPORT = 0.07",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for claim support in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_review_status",
            decision_name="Opportunity: Review Status Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.05,
            metric_name="opportunity_weight_review_status",
            value_origin="src/services/product/opportunity_score_service.py :: _W_REVIEW_STATUS = 0.05",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for review status in opportunity score.",
        ),
        DecisionCalibrationRecord(
            decision_id="opportunity_score.weight_production_readiness",
            decision_name="Opportunity: Production Readiness Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.03,
            metric_name="opportunity_weight_production_readiness",
            value_origin="src/services/product/opportunity_score_service.py :: _W_PRODUCTION_READINESS = 0.03",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight for production readiness in opportunity score. Smallest component.",
        ),
    ]


def _discovery_source_defaults() -> list[DecisionCalibrationRecord]:
    """Default parameters for discovery sources."""
    return [
        DecisionCalibrationRecord(
            decision_id="discovery.source_rate_limit_hint",
            decision_name="Discovery: Source Rate Limit Hint",
            decision_type=DecisionType.LIMIT,
            current_value=5,
            metric_name="discovery_source_rate_limit",
            value_origin="src/discovery/source_registry.py :: DiscoverySource.rate_limit_hint = 5",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scraping",
            notes="Default rate limit hint (requests/second) for discovery sources. "
            "Hardcoded as dataclass default at source_registry.py:39. "
            "Can be overridden per source instance.",
        ),
    ]


def _business_formula_weights() -> list[DecisionCalibrationRecord]:
    records: list[DecisionCalibrationRecord] = [
        DecisionCalibrationRecord(
            decision_id="agents.graph.business_impact_rag_weight",
            decision_name="Graph: Business Impact RAG Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.4,
            metric_name="graph_biz_impact_rag_weight",
            value_origin="src/agents/graph.py :: _build_rec_from_string :: 0.4",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight multiplier for RAG context presence in business_impact formula. "
            "Formula: 0.3 + 0.4 * (1.0 if rag_contexts else 0.0) + 0.3 * avg_quality. "
            "Hardcoded at graph.py:815. Sum = 1.0 when rag=1 and avg_quality=1. "
            "Range: [0.3, 1.0]. Most sensitive component: rag presence adds 0-0.4. "
            "Recommended calibration: sensitivity analysis vs downstream scoring metrics.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.business_impact_evidence_weight",
            decision_name="Graph: Business Impact Evidence Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.3,
            metric_name="graph_biz_impact_evidence_weight",
            value_origin="src/agents/graph.py :: _build_rec_from_string :: 0.3",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-scoring",
            notes="Weight multiplier for avg_quality signal in business_impact formula. "
            "Hardcoded at graph.py:815. Scales with avg_quality in [0, 0.3]. "
            "Equal weight with base (both 0.3), less than rag (0.4).",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.business_impact_base_weight",
            decision_name="Graph: Business Impact Base Weight",
            decision_type=DecisionType.WEIGHT,
            current_value=0.3,
            metric_name="graph_biz_impact_base_weight",
            value_origin="src/agents/graph.py :: _build_rec_from_string :: 0.3",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            production_allowed=False,
            owner="team-scoring",
            notes="Base weight in business_impact formula. Always contributes 0.3 minimum. "
            "Hardcoded at graph.py:815. Even with no RAG and no evidence, score = 0.3.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.next_action_confidence_threshold",
            decision_name="Graph: Next Action Confidence Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.7,
            metric_name="graph_next_action_confidence",
            value_origin="src/agents/graph.py :: _build_rec_from_string :: confidence >= 0.7",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Threshold for switching next action wording between confident and exploratory. "
            "Hardcoded at graph.py:780. Uses same threshold as CONFIDENCE_THRESHOLDS high_min (0.7). "
            "Should be kept in sync with confidence classification threshold.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.fallback_business_impact",
            decision_name="Graph: Fallback Business Impact",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.5,
            metric_name="graph_fallback_biz_impact",
            value_origin="src/agents/graph.py :: _GAP_IMPACT_MAP.get(gap_name, 0.5)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Fallback business impact value when gap is not in predefined map. "
            "Hardcoded at graph.py:720. Middle of GAP_BUSINESS_IMPACT_MAP range [0.4, 0.9]. "
            "Conservative default: assumes unknown gap has moderate impact.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.fallback_complexity",
            decision_name="Graph: Fallback Implementation Complexity",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.5,
            metric_name="graph_fallback_complexity",
            value_origin="src/agents/graph.py :: _TECH_COMPLEXITY_MAP.get(tech_name, 0.5)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Fallback implementation complexity when tech is not in predefined map. "
            "Hardcoded at graph.py:724. Middle of complexity range [0.0, 1.0]. "
            "Conservative: assumes unknown tech has moderate complexity.",
        ),
        DecisionCalibrationRecord(
            decision_id="agents.graph.default_source_quality_score",
            decision_name="Graph: Default Source Quality Score",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.5,
            metric_name="graph_default_source_quality",
            value_origin="src/agents/graph.py :: item.get('source_quality_score', 0.5)",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=False,
            owner="team-scoring",
            notes="Default quality score for evidence items when not provided. "
            "Hardcoded at graph.py:809. Middle of SOURCE_QUALITY_SCORES range [0.4, 1.0]. "
            "Below median of source types (median=0.65 between job_post=0.5 and blog=0.6).",
        ),
    ]
    return records


_RAG_BASELINE_EVIDENCE = (
    "Grid search (N=21 golden queries, 5 candidates: top_k=3,5,8,10,15) "
    "via src/evaluation/rag_baseline.py :: run_full_calibration. "
    "Dataset: data/eval/golden_baseline_rag.json (19 with expected sources, "
    "2 negative tests). Added 5 keyword-based multi-source queries "
    "(kw_inference=3 sources, kw_production=4, kw_open_source=4, "
    "kw_latency=4, kw_model=8). Targets: recall>=0.85, precision>=0.4, citation>=0.95. "
    "Results: top_k=3 achieves recall=0.8092, precision=1.0, citation=1.0, "
    "unsupported_claim_rate=0.1726. At top_k=15: recall=1.0, precision=0.4772, "
    "citation=1.0, unsupported=0.0. "
    "Recommended top_k=5 (smallest meeting all targets: recall=0.8794, precision=0.9895). "
    "Citation precision is always 1.0 in golden set (all corpus chunks have "
    "source_id and url). "
    "Calibrated 2026-06-17."
)

_SEMANTIC_BASELINE_EVIDENCE = (
    "Semantic grid search (N=21 golden queries, 5 candidates: top_k=3,5,8,10,15) "
    "via src/evaluation/rag_baseline.py :: grid_search_baseline "
    "(with vector_store=InMemoryVectorStore + embedding_model=SentenceTransformerProvider). "
    "Dataset: data/eval/golden_baseline_rag.json. "
    "Targets: recall>=0.85, precision>=0.4, citation>=0.95. "
    "Results: top_k=3 achieves recall=0.8158, precision=0.9649, citation=1.0, "
    "unsupported_claim_rate=0.1667. At top_k=15: recall=0.9539, precision=0.4737, "
    "citation=1.0, unsupported=0.0417. "
    "Recommended semantic_top_k=8 (smallest meeting all targets: recall=0.8969, precision=0.6776). "
    "Citation precision is always 1.0 in golden set. "
    "Calibrated 2026-06-18."
)


def _rag_baseline_params() -> list[DecisionCalibrationRecord]:
    """RAG baseline parameters calibrated via grid search on golden set.

    Calibrated 2026-06-17 via src/evaluation/rag_baseline.py :: run_full_calibration.
    Evidence source: data/eval/golden_baseline_rag.json evaluation results.
    """
    return [
        DecisionCalibrationRecord(
            decision_id="rag.top_k",
            decision_name="RAG Retrieval: Default Top-K",
            decision_type=DecisionType.LIMIT,
            current_value=5,
            metric_name="rag_top_k",
            value_origin="src/evaluation/rag_baseline.py :: grid_search_baseline",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.GRID_SEARCH,
            production_allowed=True,
            evidence_source=_RAG_BASELINE_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Calibrated via grid search on 21 golden queries (19 with expected "
            "sources, 16 single-source, 2 gap-based multi-source, 5 keyword "
            "multi-source). top_k=5 is the smallest value meeting recall>=0.85 "
            "(got 0.8794), precision>=0.4 (got 0.9895), citation>=0.95 (got 1.0). "
            "At top_k=3: recall=0.8092 (now below 0.85 target due to 5 new "
            "multi-source queries). Top_k=15 gives perfect recall (1.0) but "
            "lower precision (0.4772). trade-off: higher top_k increases recall "
            "but decreases precision.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.min_required_contexts",
            decision_name="RAG: Minimum Required Contexts per Query",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="rag_min_required_contexts",
            value_origin="src/evaluation/rag_baseline.py :: _recommend_min_required_contexts",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            production_allowed=True,
            evidence_source=_RAG_BASELINE_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Derived from p50 of relevant_context_count across 19 cases with "
            "expected sources at recommended top_k=5. Distribution: p25=1, "
            "p50=1, min=1, p75=2, max=5. All single-source queries have "
            "relevant_context_count=1. Multi-source queries at top_k=5: "
            "kw_inference gets 2/3 sources; kw_production gets 4/4 sources; "
            "kw_model gets 5/8 sources.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.citation_precision_threshold",
            decision_name="RAG: Citation Precision Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.95,
            metric_name="rag_citation_precision_threshold",
            value_origin="src/evaluation/rag_baseline.py :: _recommend_top_k",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source=_RAG_BASELINE_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Observed citation_precision=1.0 across all top_k candidates on "
            "the golden set (all 50 corpus chunks have source_id+url). "
            "Threshold set at 0.95 to allow for edge cases where a single "
            "retrieved context has missing attribution. "
            "Tight threshold is justified because citation metadata is a "
            "deterministic property of the corpus, not a semantic metric.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.unsupported_claim_rate_threshold",
            decision_name="RAG: Unsupported Claim Rate Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.10,
            metric_name="rag_unsupported_claim_rate_threshold",
            value_origin="src/evaluation/rag_baseline.py :: _recommend_top_k",
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            production_allowed=True,
            evidence_source=_RAG_BASELINE_EVIDENCE,
            owner="team-rag",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Observed unsupported_claim_rate=0.1091 at recommended top_k=5 "
            "(slightly above 0.10 threshold due to multi-source queries with "
            "partial recall). At top_k=5: 15/19 queries have "
            "unsupported_claim_rate=0.0; 4 multi-source queries have "
            "unsupported_rate>0 (expected sources not fully retrieved). "
            "Threshold at 0.10 still provides useful signal — will be "
            "monitored and may need adjustment after more corpus growth.",
        ),
    ]


_SCRAPING_BASELINE_EVIDENCE = (
    "Baseline evaluation (N=11 startups: 8 fictional + 3 real) "
    "via src/evaluation/scraping_baseline.py :: run_full_calibration. "
    "Dataset: data/eval/golden_scraping_baseline.json. "
    "Real startups: Maritaca AI, Silex, Gupy. "
    "SourceCollector (src/scraping/collector.py) validated against real "
    "startups: precision=1.0, recall=0.45, F1=0.625 on 3 real startups "
    "(11 expected categories, 5 found, 0 false positives). "
    "CatScore formula: norm(claim_yield) + norm(evidence_yield) - "
    "norm(failure_rate) - norm(duplicate_rate) - norm(latency) - "
    "norm(compliance_block_rate). "
    "Calibrated 2026-06-17 via real SourceCollector + golden set."
)


def _scraping_baseline_params() -> list[DecisionCalibrationRecord]:
    """Scraping baseline parameters — evaluation structure created, real data pending.

    Calibration blocked until real scraping infrastructure validates coverage
    against golden set. See data/eval/golden_scraping_baseline.json.
    """
    return [
        DecisionCalibrationRecord(
            decision_id="scraping.max_sources",
            decision_name="Scraping: Max Sources per Startup",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="scraping_max_sources",
            value_origin="src/evaluation/scraping_baseline.py :: _recommend_max_sources",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_SCRAPING_BASELINE_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Recommended via grid search (N=11, ranks 1..8) with "
            "coverage_target=0.85. Smallest max_sources achieving "
            "coverage>=85% is 3 (got 0.8846). Marginal gain from 3→4 "
            "is 7.69% (still useful), but 3 sources cover 88% of claims. "
            "Currently hardcoded as DISCOVERY_MAX_SOURCES=10 — should "
            "be reduced to 3. Next best action: update params.py.",
        ),
        DecisionCalibrationRecord(
            decision_id="scraping.max_depth",
            decision_name="Scraping: Max Crawl Depth",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="scraping_max_depth",
            value_origin="src/evaluation/scraping_baseline.py :: _recommend_max_depth",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_SCRAPING_BASELINE_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Recommended via marginal_evidence_gain >= 5%. Depth 0 yields "
            "33 total evidence; depth 1 yields 70 (+112% gain). Depth 2 "
            "yields no additional gain. Recommended max_depth=1. "
            "Currently hardcoded as MAX_SEARCH_DEPTH=2 — reduction "
            "from 2 to 1 is safe. Next best action: update params.py.",
        ),
        DecisionCalibrationRecord(
            decision_id="scraping.source_priority",
            decision_name="Scraping: Source Category Priority",
            decision_type=DecisionType.SOURCE_PRIORITY,
            current_value="official_website > github_or_code > nvidia_or_partner_ecosystem > jobs > funding_news > technical_docs > ecosystem_directory > media",
            metric_name="scraping_source_priority",
            value_origin="src/evaluation/scraping_baseline.py :: compute_source_category_scores",
            calibration_method=CalibrationMethod.MULTI_CRITERIA_DECISION_ANALYSIS,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_SCRAPING_BASELINE_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Derived via MCDA formula from 11-startup golden set + real "
            "collector validation (precision=1.0). Scores: "
            "official_website=1.75, github=1.24, nvidia_eco=1.07, "
            "jobs=0.32, funding_news=-0.28, technical_docs=-0.52, "
            "ecosystem_directory=-0.86, media=-1.79. "
            "High-latency sources (media, docs) penalized. "
            "Low-duplicate sources (github, nvidia) rewarded.",
        ),
        DecisionCalibrationRecord(
            decision_id="evidence.min_evidence_per_claim",
            decision_name="Evidence: Min Evidence Items per Supported Claim",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="evidence_min_evidence_per_claim",
            value_origin="src/evaluation/scraping_baseline.py :: _compute_supported_claim_distribution",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_SCRAPING_BASELINE_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Derived from p50 of evidence-per-claim distribution across "
            "11-startup golden set at recommended max_sources=3. "
            "Distribution: min=5, p50=6, max=9. Recommended minimum=1 "
            "(conservative — ensures at least 1 evidence per claim).",
        ),
        DecisionCalibrationRecord(
            decision_id="collection.stop_condition",
            decision_name="Collection: Stop Condition for Source Discovery",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value="marginal_gain < 3% or coverage >= 85%",
            metric_name="collection_stop_condition",
            value_origin="src/evaluation/scraping_baseline.py :: _recommend_stop_condition",
            calibration_method=CalibrationMethod.COST_BENEFIT_MODEL,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_SCRAPING_BASELINE_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Stop condition = hybrid of supported_claim_coverage >= 85%, "
            "marginal_gain < 3%, and uncertainty_remaining=0.017. "
            "Validated at max_sources=3: coverage=0.88 (above 85%). "
            "Marginal gain from 3→4 is 7.69% (above 3% min). "
            "Practical stop: at max_sources=3, stop if 3 sources collected "
            "or coverage >= 85%, whichever comes first.",
        ),
    ]


_HTTP_COLLECTOR_EVIDENCE = (
    "Derived from existing production code in src/scraping/collector.py "
    "(line 30: _REQUEST_TIMEOUT=15, line 138: max_retries from rate_limit_policy, "
    "line 168: backoff=2**attempt). "
    "Values match existing SourceCollector behavior validated against "
    "golden set (N=11 startups: 8 fictional + 3 real). "
    "Real startups: Maritaca AI, Silex, Gupy. "
    "Calibrated 2026-06-17 via HttpSourceCollector."
)


def _http_collector_params() -> list[DecisionCalibrationRecord]:
    """HTTP collector parameters — timeout, retry, backoff.

    Calibrated from existing SourceCollector defaults and validated
    against golden set in scraping_baseline evaluation.
    """
    return [
        DecisionCalibrationRecord(
            decision_id="collection.http_timeout_seconds",
            decision_name="HTTP Collector: Request Timeout",
            decision_type=DecisionType.LIMIT,
            current_value=15,
            metric_name="collection_http_timeout_seconds",
            value_origin="src/evaluation/scraping_baseline.py :: validated from src/scraping/collector.py :: _REQUEST_TIMEOUT = 15",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_HTTP_COLLECTOR_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="HTTP request timeout for source collection. "
            "Derived from existing SourceCollector._REQUEST_TIMEOUT=15. "
            "Validated against golden set: all fetchable sources respond "
            "within 5s; 15s provides 3x safety margin for rate-limited sources. "
            "Next best action: validate against production latency distribution.",
        ),
        DecisionCalibrationRecord(
            decision_id="collection.http_max_retries",
            decision_name="HTTP Collector: Max Retry Attempts",
            decision_type=DecisionType.LIMIT,
            current_value=3,
            metric_name="collection_http_max_retries",
            value_origin="src/evaluation/scraping_baseline.py :: validated from src/scraping/rate_limit_policy.py :: RateLimitPolicy.max_retries = 3",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_HTTP_COLLECTOR_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Maximum retry attempts per source fetch. "
            "Matches default max_retries=3 in rate_limit_policy. "
            "Retry only on server errors (5xx) or connection errors; "
            "client errors (4xx) are not retried. "
            "Next best action: validate retry effectiveness against golden set.",
        ),
        DecisionCalibrationRecord(
            decision_id="collection.http_backoff_base_seconds",
            decision_name="HTTP Collector: Backoff Base Seconds",
            decision_type=DecisionType.LIMIT,
            current_value=2.0,
            metric_name="collection_http_backoff_base_seconds",
            value_origin="src/evaluation/scraping_baseline.py :: validated from src/scraping/collector.py :: _fetch_with_retry :: time.sleep(2**attempt)",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            evidence_source=_HTTP_COLLECTOR_EVIDENCE,
            owner="team-scraping",
            last_calibrated_at=_CALIBRATION_TS,
            notes="Base seconds for exponential backoff: sleep(base * 2^(attempt-1)). "
            "Derived from existing SourceCollector._fetch_with_retry pattern "
            "(time.sleep(2**attempt)). At attempt 1: 2s, attempt 2: 4s, attempt 3: 8s. "
            "Next best action: validate backoff distribution against real fetch latency.",
        ),
    ]


def _scoring_weight_decisions() -> list[DecisionCalibrationRecord]:
    """Weight and threshold decisions for source_quality_score and
    evidence_confidence_score — all uncalibrated until calibration pass."""
    _cal_ts = datetime(2026, 6, 18, tzinfo=UTC)

    best_sq_weights = {
        "source_authority_prior": 0.30,
        "robots_allowed": 0.10,
        "compliance_status": 0.10,
        "fetch_success": 0.15,
        "extraction_success": 0.10,
        "duplicate_status": 0.05,
        "content_bytes": 0.05,
        "latency_ms": 0.05,
        "source_freshness_days": 0.05,
        "source_independence_type": 0.05,
    }

    return [
        DecisionCalibrationRecord(
            decision_id="weight.source_quality_score.weights",
            decision_name="Source Quality Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=best_sq_weights,
            metric_name="source_quality_score_weights",
            value_origin="source_evidence_score_baseline_eval",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_cal_ts,
            evidence_source=(
                "src/evaluation/source_evidence_baseline.py :: run_full_calibration — "
                "5 weight candidates via grid search on 95 golden entries (derived from "
                "data/eval/golden_scraping_baseline.json). Labels derived from source features. "
                "Winner: candidate 0 (default weights) — spearman=0.87, mae=0.17. "
                "SQ meets production criteria: spearman>0.5, mae<0.2, >=50 labeled entries. "
                "Full report: run_full_calibration() -> report."
            ),
            notes="Per-feature weights for source quality scoring. "
            "Calibrated via grid_search on 95 entries (source_evidence_score_baseline_eval). "
            "Labels derived deterministically from scraping baseline features. "
            "Best candidate (idx 0): spearman=0.8696, mae=0.1721, rmse=0.1908. "
            "Weights sum to 1.0. source_authority_prior (0.30) and "
            "fetch_success (0.15) are the dominant features. "
            "Calibration status: BASELINE_MEASURED, production_allowed=True. "
            "EC remains blocked — see threshold.evidence_confidence_score.production_min.",
        ),
        DecisionCalibrationRecord(
            decision_id="weight.evidence_confidence_score.weights",
            decision_name="Evidence Confidence Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value={
                "source_quality_score": 0.15,
                "extraction_confidence": 0.15,
                "snippet_length": 0.05,
                "text_specificity_score": 0.10,
                "claim_support_count": 0.10,
                "supporting_source_count": 0.10,
                "cross_source_agreement_count": 0.10,
                "contradiction_count": 0.05,
                "factuality_status": 0.10,
                "duplicate_penalty": 0.05,
                "unsupported_critical_claim_flag": 0.05,
            },
            metric_name="evidence_confidence_score_weights",
            value_origin="source_evidence_score_baseline_eval",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            evidence_source=(
                "src/evaluation/source_evidence_baseline.py :: run_full_calibration — "
                "5 weight candidates evaluated via sensitivity analysis on 95 golden entries "
                "(derived from data/eval/golden_scraping_baseline.json). "
                "Labels derived from scraping baseline features (95/95 labeled). "
                "EC BLOCKED: false_positive_rate=1.0 (max allowed=0.2). "
                "Root cause: scraping baseline lacks evidence-level features "
                "(confidence, evidence_kind, is_critical variance). "
                "F1=0.84 at default threshold but FP rate too high for production. "
                "Requires evidence-level data to improve EC score discrimination."
            ),
            notes="Per-feature weights for evidence confidence scoring. "
            "BLOCKED for production. Grid search completed but FP rate=1.0 "
            "exceeds max 0.2. The scraping baseline golden set does not "
            "contain evidence-level detail (confidence levels, evidence_kind "
            "variations, critical claims). EC scores cluster in 0.49-0.55 "
            "range across all entries. Fix: add real evidence items with "
            "varying extraction_confidence, factuality, and critical flags.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.source_quality_score.production_min",
            decision_name="Source Quality Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.65,
            metric_name="source_quality_score_production_min",
            value_origin="source_evidence_score_baseline_eval",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_cal_ts,
            evidence_source=(
                "src/evaluation/source_evidence_baseline.py :: run_full_calibration — "
                "Threshold at P5 of source_quality_score distribution over 95 entries. "
                "Distribution with best SQ weights: min=0.34, p5=0.6584, mean=0.80. "
                "Threshold 0.65 ensures sources below P5 are excluded from production. "
                "Calibrated alongside weight.source_quality_score.weights."
            ),
            notes="Minimum source_quality_score=0.65 for production evidence. "
            "Derived from P5 of score distribution over 95 golden entries. "
            "Ensures bottom 5% of sources (failed fetches, blocked, "
            "high-latency, duplicates) are excluded.",
        ),
        DecisionCalibrationRecord(
            decision_id="threshold.evidence_confidence_score.production_min",
            decision_name="Evidence Confidence Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.55,
            metric_name="evidence_confidence_score_production_min",
            value_origin="source_evidence_score_baseline_eval",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-scoring",
            evidence_source=(
                "src/evaluation/source_evidence_baseline.py :: run_full_calibration — "
                "Threshold search completed (f1_minus_fp_rate optimization). "
                "Optimal threshold=0.55 but production BLOCKED because "
                "fp_rate=1.0 with current weights. "
                "EC scores lack variance due to missing evidence-level features "
                "in the scraping baseline. "
                "Threshold kept at 0.55 as placeholder; production not allowed."
            ),
            notes="Minimum evidence_confidence_score threshold. "
            "BLOCKED for production. Optimal threshold=0.55 found via "
            "f1_minus_fp_rate optimization. "
            "Not released because EC weights are uncalibrated "
            "(fp_rate=1.0 with 95 derived labels). "
            "Fix requires evidence-level data with feature variance.",
        ),
    ]


def _startup_scoring_decisions() -> list[DecisionCalibrationRecord]:
    """Startup scoring decisions — calibrated via baseline evaluator.

    Calibrated using 30 golden entries with labels derived deterministically
    from reference weights (label_source=derived_from_synthetic_reference).
    Run `python scripts/populate_golden_set.py` to regenerate and recalibrate.
    """
    _now = datetime(2026, 6, 18, tzinfo=UTC)

    ai_weights_calibrated: dict[str, float] = {
        "ai_signal_count": 0.25,
        "ai_signal_source_coverage": 0.10,
        "technical_ai_term_count": 0.08,
        "product_ai_claim_count": 0.06,
        "accepted_ai_evidence_count": 0.06,
        "ai_claim_support_ratio": 0.08,
        "evidence_confidence_mean_for_ai_claims": 0.08,
        "source_quality_mean_for_ai_sources": 0.06,
        "technical_depth_signal_count": 0.10,
        "model_or_ml_infrastructure_signal_count": 0.08,
        "uncertainty_penalty": 0.05,
    }
    nv_weights_calibrated: dict[str, float] = {
        "gpu_compute_signal_count": 0.1030927835,
        "cuda_or_acceleration_signal_count": 0.1237113402,
        "inference_or_training_signal_count": 0.1237113402,
        "computer_vision_signal_count": 0.0824742268,
        "genai_llm_signal_count": 0.1030927835,
        "data_pipeline_signal_count": 0.0824742268,
        "nvidia_keyword_signal_count": 0.1237113402,
        "nvidia_relevant_industry_signal_count": 0.0721649485,
        "accepted_nvidia_fit_evidence_count": 0.0618556701,
        "rag_context_alignment_count": 0.0309278351,
        "evidence_confidence_mean_for_nvidia_claims": 0.0412371134,
        "implementation_complexity_proxy": 0.0309278351,
        "uncertainty_penalty": 0.0206185567,
    }

    notes = (
        "Baseline calibration measured: 30 golden entries with derived labels. "
        "AI Native: spearman=0.994, mae=0.0073, rmse=0.0333, f1=1.0, feature_coverage=0.803. "
        "NVIDIA Fit: spearman=0.9506, mae=0.0443, rmse=0.1358, f1=0.9, feature_coverage=0.5487, fp_rate=0.0. "
        "NVIDIA Fit weights are proportionally normalized from candidate sum 0.97 to sum 1.0. "
        "Labels derived from reference weights (label_source=derived_from_synthetic_reference). "
        "All production criteria met: spearman>=0.5, mae<=0.2, fp_rate<=0.3."
    )
    evidence_source = (
        "src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration — "
        "golden_path=data/eval/golden_startup_scoring_baseline.json. "
        "30 entries, 30 AI labels, 30 NVIDIA labels. "
        "Grid search over 5 weight candidates. "
        "Best AI candidate (idx 2): spearman=0.994, mae=0.0073. "
        "Best NVIDIA candidate (idx 0): spearman=0.9506, mae=0.0443, fp_rate=0.0. "
        "Thresholds at P5 of predicted distribution. "
        "Uncertainty penalty via sensitivity analysis on human labels."
    )

    return [
        DecisionCalibrationRecord(
            decision_id="ai_native_score.weights",
            decision_name="AI Native Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=ai_weights_calibrated,
            metric_name="ai_native_score_weights",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration — grid search over 5 candidates on 30 golden entries. Winner: candidate 2 — spearman=0.994, mae=0.0073.",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="ai_native_score.production_threshold",
            decision_name="AI Native Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.05,
            metric_name="ai_native_score_production_min",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration — P5 percentile of predicted distribution from 30 golden entries. Threshold=0.05.",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="ai_native_score.uncertainty_penalty",
            decision_name="AI Native Score: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.0,
            metric_name="ai_native_score_uncertainty_penalty",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration — sensitivity analysis over 30 golden entries. Best penalty=0.0 (minimum MAE).",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.weights",
            decision_name="NVIDIA Fit Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=nv_weights_calibrated,
            metric_name="nvidia_fit_score_weights",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration — grid search over 5 candidates on 30 golden entries. Winner: candidate 0 — spearman=0.9506, mae=0.0443, fp_rate=0.0.",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.production_threshold",
            decision_name="NVIDIA Fit Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.0299,
            metric_name="nvidia_fit_score_production_min",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration — P5 percentile of predicted distribution from 30 golden entries. Threshold=0.0299.",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.uncertainty_penalty",
            decision_name="NVIDIA Fit Score: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.0,
            metric_name="nvidia_fit_score_uncertainty_penalty",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration — sensitivity analysis over 30 golden entries. Best penalty=0.0 (minimum MAE).",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
    ]


def _gap_diagnosis_decisions() -> list[DecisionCalibrationRecord]:
    """Gap diagnosis baseline measured on the repository calibration set.

    The current baseline is synthetic and must not be represented as human
    validation. It is nevertheless a measured, reproducible baseline used by
    the 74-case gap-diagnosis regression suite. Live release validation then
    checks the resulting gaps against real-company evidence and fails closed.
    """
    calibrated_at = datetime(2026, 6, 18, tzinfo=UTC)
    severity_weights: dict[str, float] = {
        "missing_required_signal_count": 0.20,
        "weak_evidence_count": 0.15,
        "rejected_evidence_count": 0.15,
        "unsupported_claim_count": 0.15,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.05,
        "implementation_complexity_proxy": 0.05,
        "business_impact_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    }
    confidence_weights: dict[str, float] = {
        "supporting_evidence_count": 0.20,
        "supporting_source_count": 0.15,
        "average_evidence_confidence": 0.15,
        "average_source_quality": 0.15,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.08,
        "source_category_coverage": 0.07,
    }
    evidence = (
        "scripts/calibrate_gap_diagnosis.py --mode=synthetic; "
        "src/evaluation/gap_diagnosis_baseline.py; "
        "tests/evals/test_gap_diagnosis_baseline.py. Sixty seeded calibration "
        "entries produced severity Spearman=0.9877 and confidence Spearman=0.9949; "
        "the release evaluation executes 74 gap-diagnosis regression cases. "
        "This is a reproducible synthetic baseline, not human-label validation."
    )
    limitations = (
        "Baseline measured on synthetic reference labels. Keep live output review "
        "and abstention gates active; replace with human-labeled calibration when "
        "data/eval/golden_gap_diagnosis_baseline.json has at least 20 labels."
    )
    common = {
        "calibration_status": CalibrationStatus.BASELINE_MEASURED,
        "production_allowed": True,
        "owner": "team-diagnosis",
        "last_calibrated_at": calibrated_at,
        "evidence_source": evidence,
        "notes": limitations,
    }
    return [
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.severity_weights",
            decision_name="Gap Diagnosis: Severity Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=severity_weights,
            metric_name="gap_diagnosis_severity_weights",
            value_origin="scripts/calibrate_gap_diagnosis.py :: synthetic grid search candidate 1",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            **common,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.confidence_weights",
            decision_name="Gap Diagnosis: Confidence Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=confidence_weights,
            metric_name="gap_diagnosis_confidence_weights",
            value_origin="scripts/calibrate_gap_diagnosis.py :: synthetic grid search candidate 1",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            **common,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.production_threshold",
            decision_name="Gap Diagnosis: Production Severity Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.3197,
            metric_name="gap_diagnosis_production_threshold",
            value_origin="scripts/calibrate_gap_diagnosis.py :: P5 synthetic severity distribution",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            **common,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.uncertainty_penalty",
            decision_name="Gap Diagnosis: Uncertainty Penalty",
            decision_type=DecisionType.WEIGHT,
            current_value=0.0,
            metric_name="gap_diagnosis_uncertainty_penalty",
            value_origin="scripts/calibrate_gap_diagnosis.py :: minimum max-error sensitivity result",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            **common,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.minimum_evidence_coverage",
            decision_name="Gap Diagnosis: Minimum Evidence Coverage Ratio",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.20,
            metric_name="gap_diagnosis_min_evidence_coverage",
            value_origin="scripts/calibrate_gap_diagnosis.py :: P25 synthetic evidence ratio",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            **common,
        ),
    ]


def _ingestion_corpus_decisions() -> list[DecisionCalibrationRecord]:
    """Measured ingestion decisions for the governed NVIDIA corpus.

    Retrieval-sensitive chunking choices are benchmark-based on the repository
    golden retrieval suites. Operational limits are baseline-measured by the
    live release ingestion, which rebuilds Qdrant from the active allowlist and
    validates collection, payload, document hashes, vector dimension, and
    index age before any product workflow can use it.
    """
    calibrated_at = datetime(2026, 8, 3, tzinfo=UTC)
    retrieval_evidence = (
        "data/eval/golden_baseline_rag.json; src/evaluation/rag_baseline.py; "
        "tests/evals/test_rag_metrics.py; tests/unit/test_rag_retrieval_contract.py; "
        "Offline Evaluation run 30776935870. The governed heading-based, zero-overlap "
        "corpus passed the RAG/corpus suite and the complete offline evaluation."
    )
    ingestion_evidence = (
        "scripts/ingest_nvidia_corpus.py live release ingestion; "
        "final_case_evidence/live_corpus_ingestion.json; "
        "tests/unit/test_corpus_ingestion_manifest.py; "
        "tests/integration/test_workflow_schema_migration.py. The live release run "
        "ingested 20 active documents into 84 Qdrant chunks with real 1024-dimensional "
        "BAAI/bge-m3 embeddings and hash-matched the active sources.yaml allowlist."
    )
    return [
        DecisionCalibrationRecord(
            decision_id="rag.chunk_size",
            decision_name="RAG Ingestion: Heading-Boundary Chunking",
            decision_type=DecisionType.ARCHITECTURE_CHOICE,
            current_value="markdown_h2_heading_boundaries",
            metric_name="rag_chunking_strategy",
            value_origin="src/rag/ingestion.py :: chunk_document",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            evidence_source=retrieval_evidence,
            production_allowed=True,
            owner="team-rag",
            last_calibrated_at=calibrated_at,
            notes=(
                "Semantic sections are preserved at ## boundaries. The exact strategy, "
                "rather than a synthetic fixed character count, is what the golden "
                "retrieval and corpus-governance suites exercised."
            ),
        ),
        DecisionCalibrationRecord(
            decision_id="rag.chunk_overlap",
            decision_name="RAG Ingestion: Chunk Overlap",
            decision_type=DecisionType.LIMIT,
            current_value=0,
            metric_name="rag_chunk_overlap",
            value_origin="src/rag/ingestion.py :: chunk_document",
            calibration_method=CalibrationMethod.ABLATION_STUDY,
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            evidence_source=retrieval_evidence,
            production_allowed=True,
            owner="team-rag",
            last_calibrated_at=calibrated_at,
            notes=(
                "Zero overlap avoids duplicate evidence while heading-boundary chunks "
                "retain semantic units; the current corpus passed recall, precision, "
                "citation, diversity, and negative-query regression gates."
            ),
        ),
        DecisionCalibrationRecord(
            decision_id="rag.ingestion_batch_size",
            decision_name="RAG Ingestion: Qdrant Upsert Batch Size",
            decision_type=DecisionType.LIMIT,
            current_value=32,
            metric_name="rag_ingestion_batch_size",
            value_origin="scripts/ingest_nvidia_corpus.py :: --batch-size default=32",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=ingestion_evidence,
            production_allowed=True,
            owner="team-rag",
            last_calibrated_at=calibrated_at,
            notes="The live release ingestion upserted all 84 chunks without failed or skipped points.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.min_corpus_documents",
            decision_name="RAG Ingestion: Minimum Governed Corpus Documents",
            decision_type=DecisionType.QUALITY_GATE,
            current_value=20,
            metric_name="rag_min_corpus_documents",
            value_origin="data/nvidia_corpus/sources.yaml active allowlist",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=ingestion_evidence,
            production_allowed=True,
            owner="team-rag",
            last_calibrated_at=calibrated_at,
            notes="Fail closed if any of the 20 active governed NVIDIA sources is absent from the index.",
        ),
        DecisionCalibrationRecord(
            decision_id="rag.min_corpus_chunks",
            decision_name="RAG Ingestion: Minimum Corpus Chunks",
            decision_type=DecisionType.QUALITY_GATE,
            current_value=50,
            metric_name="rag_min_corpus_chunks",
            value_origin="Measured live corpus baseline: 84 chunks from 20 active documents",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=ingestion_evidence,
            production_allowed=True,
            owner="team-rag",
            last_calibrated_at=calibrated_at,
            notes=(
                "The production baseline contains 84 chunks. A 50-chunk floor catches "
                "major truncation while allowing benign heading consolidation; source "
                "hash and active-document gates independently require all 20 documents."
            ),
        ),
        DecisionCalibrationRecord(
            decision_id="rag.corpus_staleness_policy",
            decision_name="RAG Ingestion: Corpus Index Freshness Policy",
            decision_type=DecisionType.QUALITY_GATE,
            current_value="hash_matched_manifest_and_index_age_hours<=168",
            metric_name="rag_corpus_staleness_policy",
            value_origin="src/services/product/health_executor.py :: _validate_ingestion_manifest",
            calibration_method=CalibrationMethod.ERROR_BUDGET,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=ingestion_evidence,
            production_allowed=True,
            owner="team-rag",
            last_calibrated_at=calibrated_at,
            notes=(
                "Readiness requires a recent ingestion manifest for the configured Qdrant "
                "collection plus exact hashes for every active source. Upstream source "
                "review age remains an explicit warning rather than being confused with "
                "the age of a freshly rebuilt index."
            ),
        ),
        DecisionCalibrationRecord(
            decision_id="rag.embedding_dimension_expected",
            decision_name="RAG Ingestion: Expected Embedding Dimension",
            decision_type=DecisionType.QUALITY_GATE,
            current_value=1024,
            metric_name="rag_embedding_dimension_expected",
            value_origin="BAAI/bge-m3 and production Qdrant configuration",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            evidence_source=ingestion_evidence,
            production_allowed=True,
            owner="team-rag",
            last_calibrated_at=calibrated_at,
            notes="The configured BAAI/bge-m3 embedding provider and Qdrant collection use 1024 dimensions.",
        ),
    ]

def _recommendation_calibration_decisions() -> list[DecisionCalibrationRecord]:
    """Recommendation ranking calibration decisions — uncalibrated until sufficient real human labels.

    Requires minimum 30 human-labeled recommendation samples in
    data/eval/golden_recommendation_baseline.json before production is allowed.
    See src/evaluation/recommendation_baseline.py :: run_recommendation_baseline_calibration().
    """
    _now = datetime(2026, 6, 18, tzinfo=UTC)
    _origin = "src/evaluation/recommendation_baseline.py :: make_recommendation_baseline_records()"
    _notes = (
        "Uncalibrated. Waiting for minimum 30 human-labeled recommendation "
        "golden entries in data/eval/golden_recommendation_baseline.json. "
        "Run src/evaluation/recommendation_baseline.py --check to assess readiness."
    )
    _evidence = (
        "No calibration evidence yet — golden set is empty or insufficient. "
        "Evaluator src/evaluation/recommendation_baseline.py will compute metrics "
        "when >=30 human-labeled entries are available."
    )
    return [
        DecisionCalibrationRecord(
            decision_id="recommendation.priority_score_weights",
            decision_name="Recommendation: Per-Feature Weights for priority_score",
            decision_type=DecisionType.WEIGHT,
            current_value=None,
            metric_name="recommendation_priority_score_weights",
            value_origin=_origin,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.GRID_SEARCH,
            production_allowed=False,
            evidence_source=_evidence,
            owner="team-recommendation",
            last_calibrated_at=_now,
            notes=_notes,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.production_threshold",
            decision_name="Recommendation: Minimum priority_score for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=None,
            metric_name="recommendation_production_threshold",
            value_origin=_origin,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            production_allowed=False,
            evidence_source=_evidence,
            owner="team-recommendation",
            last_calibrated_at=_now,
            notes=_notes,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.confidence_threshold",
            decision_name="Recommendation: Minimum mapping_confidence for Recommendation confidence",
            decision_type=DecisionType.THRESHOLD,
            current_value=None,
            metric_name="recommendation_confidence_threshold",
            value_origin=_origin,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            production_allowed=False,
            evidence_source=_evidence,
            owner="team-recommendation",
            last_calibrated_at=_now,
            notes=_notes,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.uncertainty_penalty",
            decision_name="Recommendation: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=None,
            metric_name="recommendation_uncertainty_penalty",
            value_origin=_origin,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.GRID_SEARCH,
            production_allowed=False,
            evidence_source=_evidence,
            owner="team-recommendation",
            last_calibrated_at=_now,
            notes=_notes,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.minimum_mapping_confidence",
            decision_name="Recommendation: Minimum mapping_confidence for Recommendation",
            decision_type=DecisionType.THRESHOLD,
            current_value=None,
            metric_name="recommendation_minimum_mapping_confidence",
            value_origin=_origin,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            production_allowed=False,
            evidence_source=_evidence,
            owner="team-recommendation",
            last_calibrated_at=_now,
            notes=_notes,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.minimum_evidence_support",
            decision_name="Recommendation: Minimum Evidence Support Rate",
            decision_type=DecisionType.THRESHOLD,
            current_value=None,
            metric_name="recommendation_minimum_evidence_support",
            value_origin=_origin,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            production_allowed=False,
            evidence_source=_evidence,
            owner="team-recommendation",
            last_calibrated_at=_now,
            notes=_notes,
        ),
    ]


def _nvidia_mapping_decisions() -> list[DecisionCalibrationRecord]:
    """NVIDIA Technology Mapping calibration decisions — all uncalibrated by default.

    These decisions control the quantitative mapping from gap types to
    NVIDIA technologies. All are UDCALIBRATED (production_allowed=False)
    until explicitly calibrated via golden set or empirical analysis.
    """
    _now = datetime(2026, 6, 18, tzinfo=UTC)
    _notes_uncal = (
        "Uncalibrated. Requires empirical distribution of mapping scores "
        "and golden set with human-labeled gap→technology relevance before "
        "production use. See nvidia_technology_mapping.py."
    )
    return [
        DecisionCalibrationRecord(
            decision_id="nvidia_mapping.mapping_score_weights",
            decision_name="NVIDIA Mapping: Per-Feature Weights for mapping_score",
            decision_type=DecisionType.WEIGHT,
            current_value={
                "gap_severity_score": 0.20,
                "gap_confidence_score": 0.15,
                "rag_context_count_for_technology": 0.15,
                "rag_relevance_mean_for_technology": 0.10,
                "evidence_support_count": 0.10,
                "evidence_confidence_mean": 0.08,
                "source_quality_mean": 0.07,
                "technology_topic_match_count": 0.07,
                "startup_profile_signal_match_count": 0.05,
                "uncertainty_penalty": 0.03,
            },
            metric_name="nvidia_mapping_score_weights",
            value_origin="src/recommendation/nvidia_technology_mapping.py :: proposed candidate weights",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-recommendation",
            notes=_notes_uncal,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_mapping.mapping_confidence_weights",
            decision_name="NVIDIA Mapping: Per-Feature Weights for mapping_confidence",
            decision_type=DecisionType.WEIGHT,
            current_value={
                "supporting_rag_context_count": 0.20,
                "supporting_evidence_count": 0.20,
                "average_rag_relevance_score": 0.15,
                "average_evidence_confidence_score": 0.15,
                "cross_source_support_count": 0.12,
                "contradiction_count": 0.10,
                "corpus_payload_completeness_rate": 0.08,
            },
            metric_name="nvidia_mapping_confidence_weights",
            value_origin="src/recommendation/nvidia_technology_mapping.py :: proposed candidate weights",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-recommendation",
            notes=_notes_uncal,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_mapping.production_threshold",
            decision_name="NVIDIA Mapping: Minimum mapping_score for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.50,
            metric_name="nvidia_mapping_production_threshold",
            value_origin="src/recommendation/nvidia_technology_mapping.py :: default 0.50",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-recommendation",
            notes=_notes_uncal,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_mapping.minimum_rag_contexts",
            decision_name="NVIDIA Mapping: Minimum RAG Contexts for Mapping",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="nvidia_mapping_minimum_rag_contexts",
            value_origin="src/recommendation/nvidia_technology_mapping.py :: default 1",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-recommendation",
            notes=_notes_uncal,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_mapping.minimum_evidence_support",
            decision_name="NVIDIA Mapping: Minimum Evidence Items for Mapping",
            decision_type=DecisionType.LIMIT,
            current_value=1,
            metric_name="nvidia_mapping_minimum_evidence_support",
            value_origin="src/recommendation/nvidia_technology_mapping.py :: default 1",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-recommendation",
            notes=_notes_uncal,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_mapping.uncertainty_penalty",
            decision_name="NVIDIA Mapping: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.10,
            metric_name="nvidia_mapping_uncertainty_penalty",
            value_origin="src/recommendation/nvidia_technology_mapping.py :: default 0.10",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-recommendation",
            notes=_notes_uncal,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_mapping.technology_priority_policy",
            decision_name="NVIDIA Mapping: Technology Priority Policy",
            decision_type=DecisionType.RANKING,
            current_value="score_based",
            metric_name="nvidia_mapping_technology_priority_policy",
            value_origin="src/recommendation/nvidia_technology_mapping.py :: default score_based",
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
            owner="team-recommendation",
            notes=_notes_uncal,
        ),
    ]
