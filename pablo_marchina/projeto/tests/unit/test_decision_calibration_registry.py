from __future__ import annotations

from datetime import UTC, datetime

from src.quality.decision_calibration_registry import (
    CalibrationMethod,
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
    get_project_decision_inventory,
    list_production_blockers,
    list_uncalibrated_decisions,
    summarize_calibration_coverage,
    validate_decision_for_production,
)

_SCRAPING_IDS = {
    "scraping.max_sources",
    "scraping.max_depth",
    "scraping.source_priority",
    "evidence.min_evidence_per_claim",
    "collection.stop_condition",
    "collection.http_timeout_seconds",
    "collection.http_max_retries",
    "collection.http_backoff_base_seconds",
}


def _make_record(
    decision_id: str = "test-001",
    decision_name: str = "Test Decision",
    decision_type: DecisionType = DecisionType.THRESHOLD,
    calibration_status: CalibrationStatus = CalibrationStatus.UNCALIBRATED,
    production_allowed: bool = False,
    **kwargs: object,
) -> DecisionCalibrationRecord:
    return DecisionCalibrationRecord(
        decision_id=decision_id,
        decision_name=decision_name,
        decision_type=decision_type,
        calibration_status=calibration_status,
        production_allowed=production_allowed,
        **kwargs,
    )


class TestDecisionCalibrationRecord:
    def test_calibrated_can_be_production_allowed(self) -> None:
        record = DecisionCalibrationRecord(
            decision_id="t-002",
            decision_name="Threshold X",
            decision_type=DecisionType.THRESHOLD,
            calibration_status=CalibrationStatus.CALIBRATED,
            current_value=0.85,
            metric_name="accuracy",
            value_origin="cross-validation on 10k samples",
            calibration_method=CalibrationMethod.ROC_PR_CURVE,
            production_allowed=True,
            owner="team-ml",
            last_calibrated_at=datetime(2026, 6, 1, tzinfo=UTC),
            notes="Calibrated via ROC curve at 0.85 threshold.",
        )
        assert record.production_allowed is True
        assert record.calibration_status == CalibrationStatus.CALIBRATED

    def test_uncalibrated_cannot_be_production_allowed(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=True,
        )
        assert record.production_allowed is False
        assert record.calibration_status == CalibrationStatus.UNCALIBRATED

    def test_blocked_cannot_be_production_allowed(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.BLOCKED,
            production_allowed=True,
        )
        assert record.production_allowed is False
        assert record.calibration_status == CalibrationStatus.BLOCKED

    def test_benchmark_based_can_be_production_allowed(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.BENCHMARK_BASED,
            production_allowed=True,
        )
        assert record.production_allowed is True

    def test_baseline_measured_can_be_production_allowed(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
        )
        assert record.production_allowed is True


class TestValidateDecisionForProduction:
    def test_passes_for_calibrated_with_production_allowed(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
        )
        result = validate_decision_for_production(record)
        assert result.passed is True
        assert len(result.reasons) >= 1

    def test_fails_for_uncalibrated_with_explicit_reason(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
        )
        result = validate_decision_for_production(record)
        assert result.passed is False
        assert any("uncalibrated" in r.lower() for r in result.reasons)
        assert any("blocked" in r.lower() or "not in the allowed" in r for r in result.reasons)

    def test_fails_for_blocked_with_explicit_reason(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.BLOCKED,
            production_allowed=False,
        )
        result = validate_decision_for_production(record)
        assert result.passed is False
        assert any("blocked" in r.lower() for r in result.reasons)

    def test_fails_when_calibrated_but_production_not_allowed(self) -> None:
        record = _make_record(
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=False,
        )
        result = validate_decision_for_production(record)
        assert result.passed is False
        assert any("production_allowed is False" in r for r in result.reasons)

    def test_example_uncalibrated_blocked_in_production(self) -> None:
        record = _make_record(
            decision_id="example-uncalibrated-001",
            decision_name="Example: scoring weight W1",
            decision_type=DecisionType.WEIGHT,
            calibration_status=CalibrationStatus.UNCALIBRATED,
            production_allowed=False,
        )
        result = validate_decision_for_production(record)
        assert result.passed is False
        assert record.production_allowed is False


class TestListUncalibratedDecisions:
    def test_returns_only_uncalibrated(self) -> None:
        records = [
            _make_record("a", calibration_status=CalibrationStatus.CALIBRATED, production_allowed=True),
            _make_record("b", calibration_status=CalibrationStatus.UNCALIBRATED, production_allowed=False),
            _make_record("c", calibration_status=CalibrationStatus.BLOCKED, production_allowed=False),
            _make_record("d", calibration_status=CalibrationStatus.UNCALIBRATED, production_allowed=False),
        ]
        result = list_uncalibrated_decisions(records)
        assert len(result) == 2
        assert all(r.calibration_status == CalibrationStatus.UNCALIBRATED for r in result)


class TestListProductionBlockers:
    def test_returns_blocked_and_uncalibrated(self) -> None:
        records = [
            _make_record("a", calibration_status=CalibrationStatus.CALIBRATED, production_allowed=True),
            _make_record("b", calibration_status=CalibrationStatus.UNCALIBRATED, production_allowed=False),
            _make_record("c", calibration_status=CalibrationStatus.BLOCKED, production_allowed=False),
            _make_record("d", calibration_status=CalibrationStatus.CALIBRATED, production_allowed=False),
        ]
        result = list_production_blockers(records)
        ids = {r.decision_id for r in result}
        assert ids == {"b", "c", "d"}


class TestSummarizeCalibrationCoverage:
    def test_calculates_ratio_correctly(self) -> None:
        records = [
            _make_record("a", calibration_status=CalibrationStatus.CALIBRATED, production_allowed=True),
            _make_record("b", calibration_status=CalibrationStatus.CALIBRATED, production_allowed=True),
            _make_record("c", calibration_status=CalibrationStatus.UNCALIBRATED, production_allowed=False),
            _make_record("d", calibration_status=CalibrationStatus.BLOCKED, production_allowed=False),
            _make_record("e", calibration_status=CalibrationStatus.BENCHMARK_BASED, production_allowed=True),
        ]
        summary = summarize_calibration_coverage(records)
        assert summary["total_decisions"] == 5
        assert summary["calibrated_count"] == 2
        assert summary["uncalibrated_count"] == 1
        assert summary["blocked_count"] == 1
        assert summary["production_allowed_count"] == 3
        assert summary["calibration_coverage_ratio"] == 2 / 5

    def test_empty_list_returns_zero_ratio(self) -> None:
        summary = summarize_calibration_coverage([])
        assert summary["total_decisions"] == 0
        assert summary["calibration_coverage_ratio"] == 0.0


class TestDecisionTypes:
    def test_all_decision_types_defined(self) -> None:
        expected = {
            "threshold",
            "weight",
            "limit",
            "ranking",
            "architecture_choice",
            "quality_gate",
            "test_gate",
            "source_priority",
            "fallback_policy",
        }
        actual = {e.value for e in DecisionType}
        assert actual == expected

    def test_all_calibration_statuses_defined(self) -> None:
        expected = {"calibrated", "uncalibrated", "benchmark_based", "baseline_measured", "blocked"}
        actual = {e.value for e in CalibrationStatus}
        assert actual == expected

    def test_all_calibration_methods_defined(self) -> None:
        expected = {
            "baseline_measurement",
            "historical_distribution",
            "percentile_rule",
            "grid_search",
            "ablation_study",
            "roc_pr_curve",
            "sensitivity_analysis",
            "multi_criteria_decision_analysis",
            "benchmark_external",
            "cost_benefit_model",
            "error_budget",
            "risk_scoring",
        }
        actual = {e.value for e in CalibrationMethod}
        assert actual == expected


class TestProjectDecisionInventory:
    def test_returns_all_known_decisions(self) -> None:
        inventory = get_project_decision_inventory()
        assert len(inventory) > 0

    def test_all_decision_ids_are_unique(self) -> None:
        inventory = get_project_decision_inventory()
        ids = [r.decision_id for r in inventory]
        duplicates = {i for i in ids if ids.count(i) > 1}
        assert len(duplicates) == 0, f"Duplicate decision_ids: {duplicates}"

    def test_all_records_have_calibration_status(self) -> None:
        inventory = get_project_decision_inventory()
        missing = [r.decision_id for r in inventory if r.calibration_status is None]
        assert len(missing) == 0, f"Records without calibration_status: {missing}"

    def test_uncalibrated_records_have_production_allowed_false(self) -> None:
        inventory = get_project_decision_inventory()
        violations = [
            r.decision_id
            for r in inventory
            if r.calibration_status == CalibrationStatus.UNCALIBRATED and r.production_allowed
        ]
        assert len(violations) == 0, f"Uncalibrated records with production_allowed=True: {violations}"

    def test_calibration_coverage_ratio_is_calculated(self) -> None:
        inventory = get_project_decision_inventory()
        summary = summarize_calibration_coverage(inventory)
        assert "calibration_coverage_ratio" in summary
        assert isinstance(summary["calibration_coverage_ratio"], float)
        assert 0.0 <= summary["calibration_coverage_ratio"] <= 1.0

    def test_inventory_contains_at_least_one_real_decision(self) -> None:
        inventory = get_project_decision_inventory()
        real_ids = {r.decision_id for r in inventory}
        known_real = {
            "threshold.evidence_coverage",
            "weight.opportunity_score.defensibility",
            "threshold.motion.immediate_outreach",
            "parameter.rrf_k",
        }
        assert known_real.issubset(real_ids), f"Missing real decisions. Expected at least: {known_real - real_ids}"

    def test_no_test_only_values_in_inventory(self) -> None:
        """Verify no test-only threshold values leaked into production registry."""
        inventory = get_project_decision_inventory()
        ids = {r.decision_id for r in inventory}
        test_like_prefixes = {"test.", "mock.", "fixture."}
        leaked = {i for i in ids if any(i.startswith(p) for p in test_like_prefixes)}
        assert len(leaked) == 0, f"Test-only decision_ids in production registry: {leaked}"

    def test_quality_thresholds_are_calibrated(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if (
                rec.decision_id.startswith("threshold.")
                and rec.value_origin == "src/quality/constants.py :: THRESHOLDS"
            ):
                assert rec.calibration_status in (
                    CalibrationStatus.CALIBRATED,
                    CalibrationStatus.BENCHMARK_BASED,
                    CalibrationStatus.BLOCKED,
                ), f"{rec.decision_id} is still {rec.calibration_status}"

    def test_calibrated_thresholds_allow_production(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.calibration_status in (
                CalibrationStatus.CALIBRATED,
                CalibrationStatus.BENCHMARK_BASED,
                CalibrationStatus.BASELINE_MEASURED,
            ):
                assert (
                    rec.production_allowed is True
                ), f"{rec.decision_id} is {rec.calibration_status} but production_allowed={rec.production_allowed}"

    def test_blocked_thresholds_prevent_production(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.calibration_status == CalibrationStatus.BLOCKED:
                assert rec.production_allowed is False, f"{rec.decision_id} is blocked but production_allowed=True"

    def test_startup_scoring_decisions_are_measured(self) -> None:
        inventory = get_project_decision_inventory()
        startup_scoring_ids = {
            "ai_native_score.weights",
            "ai_native_score.production_threshold",
            "ai_native_score.uncertainty_penalty",
            "nvidia_fit_score.weights",
            "nvidia_fit_score.production_threshold",
            "nvidia_fit_score.uncertainty_penalty",
        }
        for rec in inventory:
            if rec.decision_id in startup_scoring_ids:
                assert (
                    rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                ), f"{rec.decision_id} should be BASELINE_MEASURED but is {rec.calibration_status}"
                assert rec.production_allowed is True

    def test_startup_scoring_decisions_have_value_origin(self) -> None:
        inventory = get_project_decision_inventory()
        startup_scoring_ids = {
            "ai_native_score.weights",
            "ai_native_score.production_threshold",
            "ai_native_score.uncertainty_penalty",
            "nvidia_fit_score.weights",
            "nvidia_fit_score.production_threshold",
            "nvidia_fit_score.uncertainty_penalty",
        }
        for rec in inventory:
            if rec.decision_id in startup_scoring_ids:
                assert rec.value_origin is not None
                assert "startup_scoring_baseline_calibration" in rec.value_origin

    def test_startup_scoring_decisions_have_evidence_source(self) -> None:
        inventory = get_project_decision_inventory()
        startup_scoring_ids = {
            "ai_native_score.weights",
            "ai_native_score.production_threshold",
            "ai_native_score.uncertainty_penalty",
            "nvidia_fit_score.weights",
            "nvidia_fit_score.production_threshold",
            "nvidia_fit_score.uncertainty_penalty",
        }
        for rec in inventory:
            if rec.decision_id in startup_scoring_ids:
                assert rec.evidence_source is not None
                assert len(rec.evidence_source) > 0

    def test_scoring_penalties_limits_and_workflow_thresholds_remain_uncalibrated(self) -> None:
        inventory = get_project_decision_inventory()
        uncalibrated_decisions = {
            "penalty.missing_component",
            "penalty.no_evidence_factor",
            "limit.max_signal_boost",
            "limit.discovery_max_sources",
            "limit.max_search_depth",
            "limit.packing.max_total",
            "limit.packing.max_per_technology",
            "limit.packing.max_per_gap",
            "threshold.workflow_completion_rate",
            "threshold.node_failure_count",
            "threshold.degraded_node_count",
            "threshold.workflow_duration_ms",
            "threshold.retry_count",
            "threshold.critical_node_success",
            "weight.evidence_confidence_score.weights",
            "threshold.evidence_confidence_score.production_min",
        }
        for rec in inventory:
            if rec.decision_id in uncalibrated_decisions:
                assert rec.calibration_status in (
                    CalibrationStatus.UNCALIBRATED,
                    CalibrationStatus.BLOCKED,
                ), f"{rec.decision_id} should not be production-capable but is {rec.calibration_status}"
                assert rec.production_allowed is False

    def test_classification_scores_and_motion_thresholds_are_calibrated(self) -> None:
        inventory = get_project_decision_inventory()
        calibrated_prefixes = (
            "score.classification_base.",
            "weight.source_quality.",
            "threshold.motion.",
            "threshold.composite_confidence.",
            "threshold.inception_fit_motion.",
            "threshold.confidence.",
            "weight.fusion.",
            "weight.rerank.",
            "penalty.rerank.",
            "parameter.rrf_k",
        )
        for rec in inventory:
            if rec.decision_id.startswith(calibrated_prefixes):
                assert rec.calibration_status in (
                    CalibrationStatus.BENCHMARK_BASED,
                    CalibrationStatus.CALIBRATED,
                ), f"{rec.decision_id} is still {rec.calibration_status}"
                assert rec.production_allowed is True

    def test_main_weight_sets_are_calibrated(self) -> None:
        inventory = get_project_decision_inventory()
        weight_set_prefixes = (
            "weight.priority_score.",
            "weight.opportunity_score.",
            "weight.production_readiness.",
            "weight.defensibility.",
            "weight.inception_fit.",
        )
        for rec in inventory:
            if rec.decision_id.startswith(weight_set_prefixes):
                assert rec.calibration_status in (
                    CalibrationStatus.BENCHMARK_BASED,
                    CalibrationStatus.CALIBRATED,
                ), f"{rec.decision_id} is still {rec.calibration_status}"
                assert rec.production_allowed is True

    def test_includes_quality_thresholds(self) -> None:
        inventory = get_project_decision_inventory()
        threshold_ids = {r.decision_id for r in inventory if r.decision_type == DecisionType.THRESHOLD}
        assert "threshold.evidence_coverage" in threshold_ids
        assert "threshold.unsupported_claim_rate" in threshold_ids
        assert "threshold.dossier_section_completeness" in threshold_ids
        assert "threshold.workflow_duration_ms" in threshold_ids

    def test_includes_weight_sets(self) -> None:
        inventory = get_project_decision_inventory()
        weight_ids = {r.decision_id for r in inventory if r.decision_type == DecisionType.WEIGHT}
        assert "weight.opportunity_score.defensibility" in weight_ids
        assert "weight.defensibility.ai_core" in weight_ids
        assert "weight.production_readiness.real_users" in weight_ids
        assert "weight.priority_score.confidence" in weight_ids

    def test_includes_fusion_and_reranking_params(self) -> None:
        inventory = get_project_decision_inventory()
        ids = {r.decision_id for r in inventory}
        assert "parameter.rrf_k" in ids
        assert "weight.fusion.dense_sparse" in ids
        assert "weight.rerank.boost_gap_match" in ids
        assert "penalty.rerank.no_provenance" in ids
        assert "limit.packing.max_total" in ids

    def test_includes_scoring_motion_thresholds(self) -> None:
        inventory = get_project_decision_inventory()
        threshold_ids = {r.decision_id for r in inventory if r.decision_type == DecisionType.THRESHOLD}
        assert "threshold.motion.immediate_outreach" in threshold_ids
        assert "threshold.motion.high_priority_outreach" in threshold_ids
        assert "threshold.inception_fit_motion.approach_now" in threshold_ids

    def test_inventory_summarize_calibrated_coverage(self) -> None:
        inventory = get_project_decision_inventory()
        summary = summarize_calibration_coverage(inventory)
        assert summary["total_decisions"] == len(inventory)
        assert summary["calibrated_count"] > 0
        assert summary["blocked_count"] > 0
        assert summary["uncalibrated_count"] > 0
        assert summary["production_allowed_count"] > 0
        assert 0.0 < summary["calibration_coverage_ratio"] < 1.0
        assert summary["total_decisions"] > 120, (
            f"Expected >= 120 decisions in inventory, got {summary['total_decisions']}. "
            "New codebase-inventoried decisions should increase this count."
        )

    def test_new_codebase_inventoried_decisions_are_uncalibrated(self) -> None:
        inventory = get_project_decision_inventory()
        new_prefixes = {
            "agents.rag.",
            "agents.scraper.",
            "agents.graph.",
            "activation.",
            "claim_ledger.",
            "weight.actionability.",
            "weight.review_readiness.",
            "limit.judge_",
            "limit.rag_eval.",
            "limit.structured_output_",
            "workflow.",
            "discovery.",
            "extraction.",
            "quality_service.",
            "validation.",
        }
        # Decisions that were upgraded from uncalibrated during calibration pass
        calibrated_new = {
            "confidence_float_map.activation_and_ledger_low",
            "weight.export_readiness.dossier_exists",
            "weight.export_readiness.evidence_coverage",
            "threshold.judge.faithfulness_with_evidence",
            "threshold.judge.faithfulness_without_evidence",
            "threshold.judge.answer_relevancy_with_evidence",
            "threshold.judge.answer_relevancy_without_evidence",
            "threshold.judge.groundedness_with_evidence",
            "threshold.judge.groundedness_without_evidence",
        }
        for rec in inventory:
            if any(rec.decision_id.startswith(p) for p in new_prefixes):
                assert rec.calibration_status == CalibrationStatus.UNCALIBRATED, (
                    f"{rec.decision_id} should be uncalibrated (new codebase-inventoried) "
                    f"but is {rec.calibration_status}"
                )
                assert rec.production_allowed is False, f"{rec.decision_id} should not allow production yet"
                assert rec.value_origin != "", f"{rec.decision_id} must have value_origin"
            if rec.decision_id in calibrated_new:
                assert (
                    rec.calibration_status != CalibrationStatus.UNCALIBRATED
                ), f"{rec.decision_id} was expected to be calibrated but is uncalibrated"
                assert (
                    rec.production_allowed is True
                ), f"{rec.decision_id} was calibrated but production_allowed is False"

    def test_inventory_some_block_production(self) -> None:
        inventory = get_project_decision_inventory()
        blockers = list_production_blockers(inventory)
        assert len(blockers) > 0
        assert len(blockers) < len(inventory)

    def test_scraping_baseline_records_exist(self) -> None:
        inventory = get_project_decision_inventory()
        ids = {r.decision_id for r in inventory}
        assert _SCRAPING_IDS.issubset(ids), f"Missing scraping baseline records: {_SCRAPING_IDS - ids}"

    def test_scraping_baseline_records_calibrated(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in _SCRAPING_IDS:
                assert (
                    rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                ), f"{rec.decision_id} should be BASELINE_MEASURED, got {rec.calibration_status}"
                assert rec.production_allowed is True

    def test_scraping_baseline_have_evidence_source(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in _SCRAPING_IDS:
                assert rec.evidence_source is not None, f"{rec.decision_id} must have evidence_source"
                assert len(rec.evidence_source) > 0

    def test_scraping_baseline_have_value_origin(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in _SCRAPING_IDS:
                assert rec.value_origin is not None, f"{rec.decision_id} must have value_origin"
                assert (
                    "scraping_baseline" in rec.value_origin
                ), f"{rec.decision_id} value_origin should reference scraping_baseline"

    def test_scraping_baseline_have_calibration_method(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in _SCRAPING_IDS:
                assert rec.calibration_method is not None, f"{rec.decision_id} must have calibration_method"

    def test_scraping_source_priority_is_source_priority_type(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "scraping.source_priority":
                assert rec.decision_type == DecisionType.SOURCE_PRIORITY

    def test_scraping_stop_condition_is_fallback_policy(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "collection.stop_condition":
                assert rec.decision_type == DecisionType.FALLBACK_POLICY


class TestExtendedRagDecisions:
    """New RAG gap-driven retrieval decisions are registered and uncalibrated."""

    _RAG_GAP_IDS: set[str] = {
        "rag.gap_query_top_k",
        "rag.min_contexts_per_gap",
        "rag.context_relevance_threshold",
        "rag.hybrid_retrieval_weights",
        "rag.reranker_required",
    }

    def test_all_rag_gap_decisions_registered(self) -> None:
        inventory = get_project_decision_inventory()
        registered_ids = {rec.decision_id for rec in inventory}
        missing = self._RAG_GAP_IDS - registered_ids
        assert not missing, f"Missing RAG gap decisions: {missing}"

    def test_rag_gap_decisions_status_by_design(self) -> None:
        """min_contexts_per_gap and context_relevance_threshold now baseline_measured
        after RAGAS eval; others remain uncalibrated."""
        inventory = get_project_decision_inventory()
        still_uncalibrated = {
            "rag.gap_query_top_k",
            "rag.hybrid_retrieval_weights",
            "rag.reranker_required",
        }
        for rec in inventory:
            if rec.decision_id in still_uncalibrated:
                assert rec.production_allowed is False, f"{rec.decision_id} must have production_allowed=False"
            elif rec.decision_id == "rag.min_contexts_per_gap":
                assert rec.production_allowed is True
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
            elif rec.decision_id == "rag.context_relevance_threshold":
                assert rec.production_allowed is True
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED

    def test_rag_gap_decision_types(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.gap_query_top_k":
                assert rec.decision_type == DecisionType.LIMIT
            elif rec.decision_id == "rag.min_contexts_per_gap":
                assert rec.decision_type == DecisionType.LIMIT
            elif rec.decision_id == "rag.context_relevance_threshold":
                assert rec.decision_type == DecisionType.THRESHOLD
            elif rec.decision_id == "rag.hybrid_retrieval_weights":
                assert rec.decision_type == DecisionType.WEIGHT
            elif rec.decision_id == "rag.reranker_required":
                assert rec.decision_type == DecisionType.THRESHOLD

    def test_existing_rag_baseline_decisions_unchanged(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.top_k":
                assert rec.production_allowed is True
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
            elif rec.decision_id == "rag.min_required_contexts":
                assert rec.production_allowed is True
            elif rec.decision_id == "rag.citation_precision_threshold":
                assert rec.production_allowed is True
            elif rec.decision_id == "rag.unsupported_claim_rate_threshold":
                assert rec.production_allowed is True

    def test_ragas_decisions_are_baseline_measured(self) -> None:
        """RAGAS evaluations now produce baseline_measured status after
        running the evaluator on the expanded golden set (12 samples)."""
        inventory = get_project_decision_inventory()
        ragas_ids = {
            "rag.ragas_context_precision_threshold",
            "rag.ragas_context_recall_threshold",
            "rag.ragas_faithfulness_threshold",
            "rag.ragas_answer_relevancy_threshold",
        }
        found = {rec.decision_id for rec in inventory}
        assert ragas_ids.issubset(found), f"Missing RAGAS decisions: {ragas_ids - found}"
        for rec in inventory:
            if rec.decision_id in ragas_ids:
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                assert rec.production_allowed is True
                assert rec.value_origin is not None
                assert "ragas_eval" in rec.value_origin


class TestRetrieverStrategyDecision:
    """``rag.retriever_strategy`` decision record is registered and production-ready."""

    def test_retriever_strategy_registered(self) -> None:
        inventory = get_project_decision_inventory()
        ids = {rec.decision_id for rec in inventory}
        assert "rag.retriever_strategy" in ids

    def test_retriever_strategy_is_architecture_choice(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.retriever_strategy":
                assert rec.decision_type == DecisionType.ARCHITECTURE_CHOICE

    def test_retriever_strategy_is_semantic_qdrant(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.retriever_strategy":
                assert rec.current_value == "semantic_qdrant"

    def test_retriever_strategy_is_baseline_measured(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.retriever_strategy":
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                assert rec.production_allowed is True

    def test_retriever_strategy_has_evidence_source(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.retriever_strategy":
                assert rec.evidence_source is not None
                assert "RAGAS eval" in rec.evidence_source

    def test_retriever_strategy_has_calibration_method(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.retriever_strategy":
                assert rec.calibration_method is not None
                assert rec.calibration_method == CalibrationMethod.BASELINE_MEASUREMENT

    def test_retriever_strategy_passes_production_validation(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "rag.retriever_strategy":
                result = validate_decision_for_production(rec)
                assert result.passed is True


class TestIngestionCorpusDecisions:
    """Ingestion/corpus decisions are registered and uncalibrated."""

    _INGESTION_IDS: set[str] = {
        "rag.chunk_size",
        "rag.chunk_overlap",
        "rag.ingestion_batch_size",
        "rag.min_corpus_documents",
        "rag.min_corpus_chunks",
        "rag.corpus_staleness_policy",
        "rag.embedding_dimension_expected",
    }

    def test_all_ingestion_decisions_registered(self) -> None:
        inventory = get_project_decision_inventory()
        registered_ids = {rec.decision_id for rec in inventory}
        missing = self._INGESTION_IDS - registered_ids
        assert not missing, f"Missing ingestion decisions: {missing}"

    def test_all_ingestion_decisions_are_uncalibrated(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in self._INGESTION_IDS:
                assert (
                    rec.calibration_status == CalibrationStatus.UNCALIBRATED
                ), f"{rec.decision_id} should be UNCALIBRATED but is {rec.calibration_status}"
                assert rec.production_allowed is False, f"{rec.decision_id} should have production_allowed=False"

    def test_all_ingestion_decisions_have_value_origin(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in self._INGESTION_IDS:
                assert rec.value_origin, f"{rec.decision_id} must have value_origin"

    def test_all_ingestion_decisions_have_decision_type(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in self._INGESTION_IDS:
                assert rec.decision_type is not None
                # All ingestion decisions are LIMIT or FALLBACK_POLICY
                assert rec.decision_type in (
                    DecisionType.LIMIT,
                    DecisionType.FALLBACK_POLICY,
                ), f"{rec.decision_id} has unexpected type {rec.decision_type}"
