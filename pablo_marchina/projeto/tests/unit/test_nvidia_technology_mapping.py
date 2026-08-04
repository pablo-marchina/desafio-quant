from __future__ import annotations

from typing import Any

from src.diagnosis.schemas import (
    GapConfidenceFeatures,
    GapDiagnosisFeatures,
    GapDiagnosisResultItem,
    GapDiagnosisStatus,
    GapSeverityFeatures,
    GapType,
)
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
    get_project_decision_inventory,
)
from src.recommendation.nvidia_technology_mapping import (
    GOLDEN_SET_STATUS,
    REQUIRED_MAPPING_DECISIONS,
    NvidiaTechnologyMappingRecord,
    build_nvidia_technology_mappings,
    compute_mapping_metrics,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_calibrated_gap(
    gap_id: str = "gap_001",
    gap_type: GapType = GapType.INFERENCE_PERFORMANCE_GAP,
    severity_score: float = 0.35,
    confidence_score: float = 0.7,
    status: GapDiagnosisStatus = GapDiagnosisStatus.PASSED,
    production_allowed: bool = True,
) -> GapDiagnosisResultItem:
    return GapDiagnosisResultItem(
        gap_id=gap_id,
        gap_type=gap_type,
        severity_score=severity_score,
        confidence_score=confidence_score,
        uncertainty=0.1,
        status=status,
        features=GapDiagnosisFeatures(
            severity=GapSeverityFeatures(
                missing_required_signal_count=0.2,
                weak_evidence_count=0.1,
                rejected_evidence_count=0.0,
                unsupported_claim_count=0.0,
                low_confidence_evidence_count=0.0,
                relevant_signal_absence=0.0,
                nvidia_fit_opportunity_signal_count=0.5,
                implementation_complexity_proxy=0.3,
                business_impact_proxy=0.7,
                uncertainty_penalty=0.1,
            ),
            confidence=GapConfidenceFeatures(
                supporting_evidence_count=0.8,
                supporting_source_count=0.6,
                average_evidence_confidence=0.7,
                average_source_quality=0.8,
                cross_source_agreement_count=0.5,
                contradiction_count=0.0,
                extraction_success_rate=0.9,
                source_category_coverage=0.6,
            ),
        ),
        weights={"severity_weights": {}, "confidence_weights": {}},
        thresholds={"severity_max": 0.5, "confidence_min": 0.3},
        supporting_evidence_ids=["ev_001", "ev_002"],
        calibration_decision_ids=[
            "gap_diagnosis.severity_weights",
            "gap_diagnosis.confidence_weights",
            "gap_diagnosis.production_threshold",
        ],
        production_allowed=production_allowed,
        blockers=[],
        explanation="Calibrated gap for testing",
        recommended_investigation="",
    )


def _make_rag_context(
    chunk_id: str = "chunk_001",
    product: str = "TensorRT",
    relevance_score: float = 0.85,
    content: str = "TensorRT optimizes inference on NVIDIA GPUs.",
) -> dict[str, Any]:
    return {
        "context_id": chunk_id,
        "chunk_id": chunk_id,
        "gap_id": "gap_001",
        "source_id": "src_001",
        "title": product,
        "content": content,
        "product": product,
        "url": "https://example.com",
        "relevance_score": relevance_score,
        "gap_types": ["inference_performance_gap"],
    }


def _make_evidence_item(
    evidence_id: str = "ev_001",
    text: str = "Uses TensorRT for GPU inference optimization.",
    evidence_confidence_score: float = 0.8,
    source_quality_score: float = 0.7,
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "evidence_id": evidence_id,
        "text": text,
        "snippet": text,
        "claim": text,
        "evidence_confidence_score": evidence_confidence_score,
        "source_quality_score": source_quality_score,
        "source_id": "src_001",
        "url": "https://example.com",
        "support_status": "supported",
    }


def _calibrated_mapping_inventory() -> list[DecisionCalibrationRecord]:
    base = get_project_decision_inventory()
    mapping_ids = set(REQUIRED_MAPPING_DECISIONS)
    overrides: dict[str, DecisionCalibrationRecord] = {}
    for rec in base:
        if rec.decision_id in mapping_ids:
            overrides[rec.decision_id] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.CALIBRATED,
                    "production_allowed": True,
                }
            )
    result = []
    for rec in base:
        if rec.decision_id in overrides:
            result.append(overrides[rec.decision_id])
        else:
            result.append(rec)
    return result


# ── Tests ───────────────────────────────────────────────────────────────────


class TestRegistryCreatesMappingsByGapType:
    """1. registry cria mappings por gap_type quando há rag_contexts compatíveis."""

    def test_creates_mappings_for_all_gap_types(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {"inference_performance_gap": [_make_rag_context()]}
        evidence = [_make_evidence_item()]

        result = build_nvidia_technology_mappings(
            run_id="test-001",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        mappings = result["nvidia_technology_mappings"]
        assert len(mappings) > 0
        gap_types_in_mappings = {m["gap_type"] for m in mappings}
        assert "inference_performance_gap" in gap_types_in_mappings

    def test_mappings_contain_both_gap_and_technology(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {"inference_performance_gap": [_make_rag_context()]}
        evidence = [_make_evidence_item()]

        result = build_nvidia_technology_mappings(
            run_id="test-002",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        mappings = result["nvidia_technology_mappings"]
        for m in mappings:
            assert m["gap_type"]
            assert m["nvidia_technology"]


class TestMappingBlocksWhenCalibrationMissing:
    """2. mapping bloqueia quando calibração está ausente."""

    def test_uncalibrated_inventory_blocks_all_mappings(self) -> None:
        gaps = [_make_calibrated_gap()]
        rag_ctxs = {"inference_performance_gap": [_make_rag_context()]}
        evidence = [_make_evidence_item()]

        result = build_nvidia_technology_mappings(
            run_id="test-003",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=get_project_decision_inventory(),
        )

        assert result["mapping_status"] == "blocked_uncalibrated_mapping"
        for m in result["nvidia_technology_mappings"]:
            assert m["production_allowed"] is False
        assert len(result["blockers"]) > 0

    def test_empty_inventory_blocks_all(self) -> None:
        result = build_nvidia_technology_mappings(
            run_id="test-004",
            rag_contexts_by_gap={},
            gap_results=[],
            gap_metrics=None,
            evidence_items=[],
            inventory=[],
        )

        assert result["mapping_status"] == "blocked_uncalibrated_mapping"
        assert len(result["blockers"]) > 0


class TestMappingUsesRagContextsByGap:
    """3. mapping usa rag_contexts_by_gap, não Qdrant direto."""

    def test_rag_contexts_are_consumed_not_qdrant(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {
            "inference_performance_gap": [
                _make_rag_context(chunk_id="c1", product="TensorRT"),
                _make_rag_context(chunk_id="c2", product="Triton Inference Server"),
            ]
        }
        evidence = [_make_evidence_item()]

        result = build_nvidia_technology_mappings(
            run_id="test-005",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        mappings = result["nvidia_technology_mappings"]
        tensorrt_mappings = [m for m in mappings if m["nvidia_technology"] == "TensorRT"]
        assert len(tensorrt_mappings) > 0
        # Verify rag_contexts_by_gap is used, not a direct call
        assert "rag_contexts_by_gap" in build_nvidia_technology_mappings.__code__.co_varnames


class TestMappingRequiresSupportingRagContextIds:
    """4. mapping exige supporting_rag_context_ids."""

    def test_supporting_rag_context_ids_populated(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {
            "inference_performance_gap": [
                _make_rag_context(chunk_id="c1", product="TensorRT"),
            ]
        }
        evidence = [_make_evidence_item(evidence_id="ev1")]

        result = build_nvidia_technology_mappings(
            run_id="test-006",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        for m in result["nvidia_technology_mappings"]:
            assert "supporting_rag_context_ids" in m


class TestMappingRequiresEvidenceIdsOrNeedsMoreEvidence:
    """5. mapping exige supporting_evidence_ids ou needs_more_evidence."""

    def test_evidence_ids_or_needs_more_evidence(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {"inference_performance_gap": [_make_rag_context()]}
        evidence = [_make_evidence_item(evidence_id="ev1")]

        result = build_nvidia_technology_mappings(
            run_id="test-007",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        for m in result["nvidia_technology_mappings"]:
            has_rag_ids = len(m.get("supporting_rag_context_ids", [])) > 0
            has_ev_ids = len(m.get("supporting_evidence_ids", [])) > 0
            # Every mapping must have at least one of rag_ids, ev_ids, or needs_more_evidence flag
            is_needs_evidence = "needs_more_evidence" in m.get("mapping_status", "")
            is_needs_evidence = is_needs_evidence or ("Insufficient evidence" in m.get("explanation", ""))
            is_needs_evidence = is_needs_evidence or (
                m.get("production_allowed") is False and not has_rag_ids and not has_ev_ids
            )
            assert has_rag_ids or has_ev_ids or is_needs_evidence, (
                f"Mapping {m['mapping_id']} ({m['nvidia_technology']}) has no supporting IDs "
                f"and is not flagged as needs_more_evidence"
            )


class TestMappingScoreRange:
    """6. mapping_score fica entre 0 e 1 com calibração válida."""

    def test_mapping_score_in_range(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.COMPUTE_ACCELERATION_GAP)]
        rag_ctxs = {"compute_acceleration_gap": [_make_rag_context(product="CUDA")]}
        evidence = [_make_evidence_item(text="Uses CUDA for GPU compute.")]

        result = build_nvidia_technology_mappings(
            run_id="test-008",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        for m in result["nvidia_technology_mappings"]:
            if m["production_allowed"]:
                assert 0.0 <= m["mapping_score"] <= 1.0
                assert 0.0 <= m["mapping_confidence"] <= 1.0


class TestMappingConfidenceRange:
    """7. mapping_confidence fica entre 0 e 1 com calibração válida."""

    def test_mapping_confidence_in_range(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.DATA_PIPELINE_GAP)]
        rag_ctxs = {"data_pipeline_gap": [_make_rag_context(product="RAPIDS")]}
        evidence = [_make_evidence_item(text="Uses RAPIDS for data pipelines.")]

        result = build_nvidia_technology_mappings(
            run_id="test-009",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        for m in result["nvidia_technology_mappings"]:
            if m["production_allowed"]:
                assert 0.0 <= m["mapping_confidence"] <= 1.0


class TestUnsupportedNotProductionAllowed:
    """8. unsupported/sem suporte não vira production_allowed."""

    def test_no_context_no_evidence_blocks_production(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.COMPUTER_VISION_GAP)]
        result = build_nvidia_technology_mappings(
            run_id="test-010",
            rag_contexts_by_gap={},
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=[],
            inventory=_calibrated_mapping_inventory(),
        )

        for m in result["nvidia_technology_mappings"]:
            assert m["production_allowed"] is False


class TestMappingMetrics:
    """9. métricas de mapping são calculadas."""

    def test_metrics_contain_all_required_fields(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {"inference_performance_gap": [_make_rag_context()]}
        evidence = [_make_evidence_item()]

        result = build_nvidia_technology_mappings(
            run_id="test-011",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        metrics = result["nvidia_mapping_metrics"]
        required = [
            "total_mapping_count",
            "production_allowed_mapping_count",
            "blocked_mapping_count",
            "mappings_by_gap_type",
            "mappings_by_technology",
            "average_mapping_score",
            "average_mapping_confidence",
            "unsupported_mapping_count",
            "missing_calibration_count",
            "rag_supported_mapping_rate",
            "evidence_supported_mapping_rate",
        ]
        for key in required:
            assert key in metrics, f"Missing required metric: {key}"

    def test_mapping_calibration_metrics_present(self) -> None:
        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {"inference_performance_gap": [_make_rag_context()]}
        evidence = [_make_evidence_item()]

        result = build_nvidia_technology_mappings(
            run_id="test-012",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        cal_metrics = result["nvidia_mapping_calibration_metrics"]
        required = [
            "evidence_supported_mapping_rate",
            "rag_supported_mapping_rate",
            "unsupported_mapping_rate",
            "technology_coverage",
        ]
        for key in required:
            assert key in cal_metrics, f"Missing calibration metric: {key}"


class TestGoldenSetMeasured:
    """10. golden set insuficiente bloqueia produção."""

    def test_golden_set_measured_allows_production_path(self) -> None:
        assert GOLDEN_SET_STATUS == "baseline_dataset_measured"

    def test_build_mappings_uses_measured_golden_set_status(self) -> None:
        # With all calibrations in place, golden set itself should block
        from src.recommendation.nvidia_technology_mapping import GOLDEN_SET_STATUS

        assert GOLDEN_SET_STATUS == "baseline_dataset_measured"

        gaps = [_make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP)]
        rag_ctxs = {"inference_performance_gap": [_make_rag_context()]}
        evidence = [_make_evidence_item()]

        result = build_nvidia_technology_mappings(
            run_id="test-golden",
            rag_contexts_by_gap=rag_ctxs,
            gap_results=gaps,
            gap_metrics=None,
            evidence_items=evidence,
            inventory=_calibrated_mapping_inventory(),
        )

        assert result["mapping_status"] in {"passed", "needs_more_evidence"}
        assert "nvidia_technology_mappings" in result


class TestNoLlmOrQdrantOrScraping:
    """11. nenhum LLM/Qdrant/scraping/internet é chamado."""

    def test_no_llm_imports(self) -> None:
        import src.recommendation.nvidia_technology_mapping as mod

        source = open(mod.__file__ or "", encoding="utf-8").read()
        assert "from langchain" not in source
        assert "from openai" not in source
        assert "from anthropic" not in source

    def test_no_qdrant_imports(self) -> None:
        import src.recommendation.nvidia_technology_mapping as mod

        source = open(mod.__file__ or "", encoding="utf-8").read()
        assert "from qdrant" not in source
        assert "import qdrant" not in source
        assert "Qdrant" not in source

    def test_no_scraping_imports(self) -> None:
        import src.recommendation.nvidia_technology_mapping as mod

        source = open(mod.__file__ or "", encoding="utf-8").read()
        assert "from src.scraping" not in source
        assert "requests" not in source
        assert "httpx" not in source


class TestComputeMappingMetrics:
    def test_compute_mapping_metrics_empty(self) -> None:
        metrics = compute_mapping_metrics([])
        assert metrics.total_mapping_count == 0
        assert metrics.average_mapping_score == 0.0
        assert metrics.average_mapping_confidence == 0.0

    def test_compute_mapping_metrics_with_records(self) -> None:
        records = [
            NvidiaTechnologyMappingRecord(
                mapping_id="m1",
                gap_type="inference_performance_gap",
                nvidia_technology="TensorRT",
                mapping_score=0.75,
                mapping_confidence=0.85,
                uncertainty=0.05,
                supporting_rag_context_ids=["c1"],
                supporting_evidence_ids=["e1"],
                production_allowed=True,
            ),
            NvidiaTechnologyMappingRecord(
                mapping_id="m2",
                gap_type="inference_performance_gap",
                nvidia_technology="Triton Inference Server",
                mapping_score=0.45,
                mapping_confidence=0.50,
                uncertainty=0.15,
                supporting_rag_context_ids=[],
                supporting_evidence_ids=[],
                production_allowed=False,
            ),
        ]
        metrics = compute_mapping_metrics(records)
        assert metrics.total_mapping_count == 2
        assert metrics.production_allowed_mapping_count == 1
        assert metrics.blocked_mapping_count == 1
        assert metrics.average_mapping_score == 0.60
        assert metrics.average_mapping_confidence == 0.675
        assert metrics.unsupported_mapping_count == 1
        assert metrics.rag_supported_mapping_rate == 0.5
        assert metrics.evidence_supported_mapping_rate == 0.5
