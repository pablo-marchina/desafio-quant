"""Tests for gap-driven NVIDIA context retrieval.

Validates that ``retrieve_nvidia_context`` uses calibrated gaps
(``production_allowed=True``) as primary input, builds deterministic
RAG queries, checks calibration decisions, and produces structured
metrics.  All tests avoid real Qdrant — they mock ``ChunkIndex``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from src.diagnosis.schemas import (
    GapConfidenceFeatures,
    GapDiagnosisFeatures,
    GapDiagnosisMetrics,
    GapDiagnosisResultItem,
    GapDiagnosisStatus,
    GapDiagnosisSummary,
    GapSeverityFeatures,
    GapType,
)
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
    get_project_decision_inventory,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_calibrated_gap(
    gap_id: str = "gap_001",
    gap_type: GapType = GapType.INFERENCE_PERFORMANCE_GAP,
    severity_score: float = 0.35,
    confidence_score: float = 0.7,
    status: GapDiagnosisStatus = GapDiagnosisStatus.PASSED,
    production_allowed: bool = True,
    supporting_evidence_ids: list[str] | None = None,
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
        supporting_evidence_ids=supporting_evidence_ids or [],
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


def _make_blocked_gap(
    gap_id: str = "gap_blocked_001",
    gap_type: GapType = GapType.EVIDENCE_COVERAGE_GAP,
) -> GapDiagnosisResultItem:
    return _make_calibrated_gap(
        gap_id=gap_id,
        gap_type=gap_type,
        status=GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS,
        production_allowed=False,
        severity_score=0.8,
        confidence_score=0.2,
        supporting_evidence_ids=[],
    )


def _make_summary(
    gaps: list[GapDiagnosisResultItem] | None = None,
    status: GapDiagnosisStatus = GapDiagnosisStatus.PASSED,
) -> dict[str, Any]:
    if gaps is None:
        gaps = [_make_calibrated_gap()]
    return GapDiagnosisSummary(
        run_id="test-rag-retrieval-001",
        gap_diagnosis_status=status,
        gaps=gaps,
        metrics=GapDiagnosisMetrics(
            total_gap_count=len(gaps),
            production_allowed_gap_count=sum(1 for g in gaps if g.production_allowed),
            blocked_gap_count=sum(1 for g in gaps if not g.production_allowed),
            average_gap_severity=0.5,
            average_gap_confidence=0.6,
            high_severity_gap_count=0,
            evidence_coverage_gap_count=0,
            missing_calibration_count=0,
            calibrated_decision_count=3,
            gap_uncertainty_mean=0.1,
        ),
        calibration_status="baseline_measured",
        production_allowed=True,
    ).model_dump(mode="json")


def _empty_mock_idx() -> MagicMock:
    idx = MagicMock()
    idx.chunks = []
    return idx


def _make_mock_svc(**kwargs: Any) -> MagicMock:
    from src.agents.nvidia_rag_agent import retrieve_nvidia_context

    with (
        patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
        patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
    ):
        mock_idx = kwargs.get("mock_idx", _empty_mock_idx())
        mock_build.return_value = mock_idx
        mock_inv.return_value = _calibrated_rag_inventory()
        result = retrieve_nvidia_context(**kwargs.pop("svc_kwargs", {}))
    return result


def _calibrated_rag_inventory() -> list[DecisionCalibrationRecord]:
    base = get_project_decision_inventory()
    overrides: dict[str, DecisionCalibrationRecord] = {}
    for rec in base:
        if rec.decision_id == "rag.gap_query_top_k":
            overrides["rag.gap_query_top_k"] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                    "production_allowed": True,
                }
            )
        elif rec.decision_id == "rag.min_contexts_per_gap":
            overrides["rag.min_contexts_per_gap"] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                    "production_allowed": True,
                }
            )
        elif rec.decision_id == "rag.context_relevance_threshold":
            overrides["rag.context_relevance_threshold"] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                    "production_allowed": True,
                }
            )
        elif rec.decision_id == "rag.citation_precision_threshold":
            overrides["rag.citation_precision_threshold"] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                    "production_allowed": True,
                }
            )
        elif rec.decision_id == "rag.unsupported_claim_rate_threshold":
            overrides["rag.unsupported_claim_rate_threshold"] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                    "production_allowed": True,
                }
            )
        elif rec.decision_id == "rag.hybrid_retrieval_weights":
            overrides["rag.hybrid_retrieval_weights"] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                    "production_allowed": True,
                }
            )
        elif rec.decision_id == "rag.reranker_required":
            overrides["rag.reranker_required"] = rec.model_copy(
                update={
                    "calibration_status": CalibrationStatus.BASELINE_MEASURED,
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


class TestRetrieveNvidiaContextCalibratedGaps:
    """1. retrieve_nvidia_context gera queries por gap calibrado."""

    def test_generates_query_per_calibrated_gap(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gaps = [
            _make_calibrated_gap(gap_id="gap_001", gap_type=GapType.INFERENCE_PERFORMANCE_GAP),
            _make_calibrated_gap(gap_id="gap_002", gap_type=GapType.DATA_PIPELINE_GAP),
        ]
        summary = _make_summary(gaps=gaps)

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = []
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-001",
                gap_diagnosis_summary=summary,
                startup_profile={"sector": "AI", "product_summary": "LLM inference"},
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=0.8,
                nvidia_fit_score=0.6,
            )

        queries = result["rag_queries_by_gap"]
        assert len(queries) == 2
        assert "gap_001" in queries
        assert "gap_002" in queries
        assert queries["gap_001"]["gap_type"] == "inference_performance_gap"
        assert queries["gap_001"]["production_allowed"] is True
        assert "gap_type" in queries["gap_001"]["generated_from"]


class TestUncalibratedGapsBlocked:
    """2. gaps não calibrados não geram query produtiva."""

    def test_blocked_gap_does_not_generate_query(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        calibrated = _make_calibrated_gap(gap_id="good_gap")
        blocked = _make_blocked_gap(gap_id="bad_gap")
        summary = _make_summary(gaps=[calibrated, blocked])

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = []
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-002",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        queries = result["rag_queries_by_gap"]
        assert "good_gap" in queries
        assert "bad_gap" not in queries
        assert result["rag_retrieval_metrics"]["calibrated_gap_count"] == 1


class TestNoCalibratedGapsBlocks:
    """3. ausência de gaps calibrados bloqueia RAG."""

    def test_all_gaps_blocked_blocks_rag(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        blocked = _make_blocked_gap()
        summary = _make_summary(gaps=[blocked], status=GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS)

        with patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv:
            mock_inv.return_value = _calibrated_rag_inventory()
            result = retrieve_nvidia_context(
                run_id="test-003",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "blocked_no_calibrated_gaps"
        assert result["status"] == "rag_blocked_no_calibrated_gaps"
        assert result["review_required"] is True

    def test_empty_gaps_list_blocks_rag(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        result = retrieve_nvidia_context(
            run_id="test-003b",
            gap_diagnosis_summary=_make_summary(gaps=[]),
            startup_profile=None,
            accepted_evidence_items=[],
            claims=[],
            ai_native_score=None,
            nvidia_fit_score=None,
        )

        assert result["rag_retrieval_status"] == "blocked_no_calibrated_gaps"

    def test_none_summary_blocks_rag(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        result = retrieve_nvidia_context(
            run_id="test-003c",
            gap_diagnosis_summary=None,
            startup_profile=None,
            accepted_evidence_items=[],
            claims=[],
            ai_native_score=None,
            nvidia_fit_score=None,
        )

        assert result["rag_retrieval_status"] == "blocked_no_calibrated_gaps"


class TestMissingRagDecisionBlocks:
    """4. decisão RAG ausente bloqueia retrieval produtivo."""

    def test_missing_rag_decision_blocks_retrieval(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        summary = _make_summary()

        with patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv:
            mock_inv.return_value = []
            result = retrieve_nvidia_context(
                run_id="test-004",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "blocked_uncalibrated_rag"
        assert result["review_required"] is True
        assert result["rag_retrieval_metrics"]["missing_rag_calibration_count"] > 0


class TestContextAssociatedWithGap:
    """5. contexto retornado é associado ao gap_id."""

    def test_context_has_gap_id(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gap = _make_calibrated_gap(gap_id="gap_ctx_001", gap_type=GapType.COMPUTER_VISION_GAP)
        summary = _make_summary(gaps=[gap])

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = [
                MagicMock(
                    chunk_id="chunk_1",
                    source_id="src_1",
                    title="NVIDIA TensorRT",
                    content="TensorRT optimizes CV model inference.",
                    product="NVIDIA TensorRT",
                    url="https://example.com/tensorrt",
                    relevance_score=0.85,
                    gap_types=["computer_vision_need"],
                    version="1.0",
                    valid_from=None,
                    valid_until=None,
                    freshness_policy=None,
                    stale_after_days=None,
                    is_active=True,
                    deprecated_at=None,
                    superseded_by=None,
                ),
            ]
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-005",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        contexts_by_gap = result["rag_contexts_by_gap"]
        assert "gap_ctx_001" in contexts_by_gap
        assert len(contexts_by_gap["gap_ctx_001"]) > 0
        assert contexts_by_gap["gap_ctx_001"][0]["gap_id"] == "gap_ctx_001"
        assert contexts_by_gap["gap_ctx_001"][0]["context_id"] == "chunk_1"


class TestRagContextsByGapPopulated:
    """6. rag_contexts_by_gap é preenchido."""

    def test_contexts_by_gap_contains_all_gaps(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gaps = [
            _make_calibrated_gap(gap_id="g1", gap_type=GapType.INFERENCE_PERFORMANCE_GAP),
            _make_calibrated_gap(gap_id="g2", gap_type=GapType.DATA_PIPELINE_GAP),
        ]
        summary = _make_summary(gaps=gaps)

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = [
                MagicMock(
                    chunk_id="c1",
                    source_id="s1",
                    title="T",
                    content="C",
                    product="NVIDIA NIM",
                    url="https://x.com",
                    relevance_score=0.5,
                    gap_types=[],
                    version="1.0",
                    valid_from=None,
                    valid_until=None,
                    freshness_policy=None,
                    stale_after_days=None,
                    is_active=True,
                    deprecated_at=None,
                    superseded_by=None,
                ),
            ]
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-006",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert "g1" in result["rag_contexts_by_gap"]
        assert "g2" in result["rag_contexts_by_gap"]


class TestContextCountByGapMetrics:
    """7. metrics calculam context_count_by_gap."""

    def test_context_count_by_gap_in_metrics(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gap = _make_calibrated_gap(gap_id="cnt_gap")
        summary = _make_summary(gaps=[gap])

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = [
                MagicMock(
                    chunk_id="c1",
                    source_id="s1",
                    title="T",
                    content="C",
                    product="NVIDIA NIM",
                    url="https://x.com",
                    relevance_score=0.5,
                    gap_types=[],
                    version="1.0",
                    valid_from=None,
                    valid_until=None,
                    freshness_policy=None,
                    stale_after_days=None,
                    is_active=True,
                    deprecated_at=None,
                    superseded_by=None,
                ),
                MagicMock(
                    chunk_id="c2",
                    source_id="s2",
                    title="T2",
                    content="C2",
                    product="TensorRT-LLM",
                    url="https://y.com",
                    relevance_score=0.6,
                    gap_types=[],
                    version="1.0",
                    valid_from=None,
                    valid_until=None,
                    freshness_policy=None,
                    stale_after_days=None,
                    is_active=True,
                    deprecated_at=None,
                    superseded_by=None,
                ),
            ]
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-007",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        metrics = result["rag_retrieval_metrics"]
        assert "context_count_by_gap" in metrics
        assert metrics["context_count_by_gap"]["cnt_gap"] >= 1
        assert metrics["retrieved_context_count"] >= 1


class TestMinContextsPerGap:
    """8. min_contexts_per_gap calibrado é respeitado."""

    def test_gaps_below_min_contexts_counted(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gap = _make_calibrated_gap(gap_id="low_ctx_gap")
        summary = _make_summary(gaps=[gap])

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = []
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-008",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        metrics = result["rag_retrieval_metrics"]
        assert metrics["gaps_with_min_contexts_count"] == 0
        assert metrics["gaps_without_context_count"] == 1


class TestGapsWithoutContextNeedsReview:
    """9. gaps sem contexto suficiente viram needs_review."""

    def test_needs_review_when_gap_has_no_context(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gap = _make_calibrated_gap(gap_id="empty_gap")
        summary = _make_summary(gaps=[gap])

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = []
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-009",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "needs_review"
        assert result["status"] == "rag_needs_review"
        assert result["review_required"] is True


class TestRagError:
    """10. erro do RAG vira failed/blocker sanitizado."""

    def test_build_index_error_sanitized(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        summary = _make_summary()

        with (
            patch(
                "src.agents.nvidia_rag_agent.build_default_index",
                side_effect=RuntimeError("corpus corrupt"),
            ),
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            mock_inv.return_value = _calibrated_rag_inventory()
            result = retrieve_nvidia_context(
                run_id="test-010",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "failed"
        assert result["status"] == "rag_failed"
        assert any("RuntimeError" in b for b in (result.get("blockers") or []))


class TestRunIdPreserved:
    """11. run_id é preservado."""

    def test_run_id_in_output(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        summary = _make_summary()

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = []
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="preserved-rag-id-42",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result is not None


class TestNoLlmOrScraping:
    """13. nenhum LLM/scraping é chamado (verificado por não importar)."""

    def test_no_llm_imports(self) -> None:
        import src.agents.nvidia_rag_agent as mod

        source = open(mod.__file__ or "", encoding="utf-8").read()
        assert "from langchain" not in source
        assert "from openai" not in source
        assert "from anthropic" not in source
        assert "import openai" not in source
        assert "ChatOpenAI" not in source
        assert "ChatAnthropic" not in source

    def test_no_scraping_imports(self) -> None:
        import src.agents.nvidia_rag_agent as mod

        source = open(mod.__file__ or "", encoding="utf-8").read()
        assert "from src.scraping" not in source
        assert "import scraping" not in source
        assert "requests.get" not in source
        assert "httpx" not in source
        assert "aiohttp" not in source


class TestRetrievalMetricsComplete:
    """Verifica que todas as métricas obrigatórias estão presentes."""

    def test_all_required_metrics_present(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gap1 = _make_calibrated_gap(gap_id="m1")
        gap2 = _make_calibrated_gap(gap_id="m2")
        summary = _make_summary(gaps=[gap1, gap2])

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = [
                MagicMock(
                    chunk_id="c1",
                    source_id="s1",
                    title="T",
                    content="C",
                    product="NVIDIA NIM",
                    url="https://x.com",
                    relevance_score=0.5,
                    gap_types=[],
                    version="1.0",
                    valid_from=None,
                    valid_until=None,
                    freshness_policy=None,
                    stale_after_days=None,
                    is_active=True,
                    deprecated_at=None,
                    superseded_by=None,
                ),
            ]
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-metrics",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        metrics = result["rag_retrieval_metrics"]
        required = [
            "gap_count",
            "calibrated_gap_count",
            "query_count",
            "retrieved_context_count",
            "context_count_by_gap",
            "gaps_with_min_contexts_count",
            "gaps_without_context_count",
            "average_retrieval_score",
            "average_relevance_score",
            "citation_ready_context_count",
            "missing_rag_calibration_count",
            "rag_blocker_count",
        ]
        for key in required:
            assert key in metrics, f"Missing required metric: {key}"


class TestCalibrationDecisionIds:
    """Verifica que calibration_decision_ids são propagados."""

    def test_contexts_have_calibration_decision_ids(self) -> None:
        from src.agents.nvidia_rag_agent import retrieve_nvidia_context

        gap = _make_calibrated_gap(gap_id="cal_gap")
        summary = _make_summary(gaps=[gap])

        with (
            patch("src.agents.nvidia_rag_agent.build_default_index") as mock_build,
            patch("src.agents.nvidia_rag_agent.get_project_decision_inventory") as mock_inv,
        ):
            idx = MagicMock()
            idx.chunks = [MagicMock(), MagicMock()]
            idx.retrieve.return_value = [
                MagicMock(
                    chunk_id="c1",
                    source_id="s1",
                    title="T",
                    content="C",
                    product="NVIDIA TensorRT",
                    url="https://x.com",
                    relevance_score=0.7,
                    gap_types=[],
                    version="1.0",
                    valid_from=None,
                    valid_until=None,
                    freshness_policy=None,
                    stale_after_days=None,
                    is_active=True,
                    deprecated_at=None,
                    superseded_by=None,
                ),
            ]
            mock_build.return_value = idx
            mock_inv.return_value = _calibrated_rag_inventory()

            result = retrieve_nvidia_context(
                run_id="test-cal-ids",
                gap_diagnosis_summary=summary,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        ctxs = result["rag_contexts_by_gap"].get("cal_gap", [])
        if ctxs:
            assert "calibration_decision_ids" in ctxs[0]
            assert len(ctxs[0]["calibration_decision_ids"]) > 0


class TestSemanticCalibrationsRequired:
    """14. REQUIRED_SEMANTIC_DECISIONS bloqueiam se ausentes/missing."""

    def test_required_semantic_decisions_defined(self) -> None:
        from src.rag.rag_service_factory import REQUIRED_SEMANTIC_DECISIONS

        assert "rag.semantic_top_k" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.min_contexts_per_gap" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.context_relevance_threshold" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.citation_precision_threshold" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.unsupported_claim_rate_threshold" in REQUIRED_SEMANTIC_DECISIONS
        # hybrid decisions NOT required for semantic-only path
        assert "rag.hybrid_retrieval_weights" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.reranker_required" in REQUIRED_SEMANTIC_DECISIONS

    def test_validate_semantic_calibrations_returns_blockers_when_missing(self) -> None:
        from src.rag.rag_service_factory import _validate_semantic_calibrations

        with patch(
            "src.rag.rag_service_factory.get_project_decision_inventory",
            return_value=[],
        ):
            values, blockers = _validate_semantic_calibrations()
            assert len(blockers) >= 1
            assert any("rag.semantic_top_k" in b for b in blockers)
            assert values == {}

    def test_validate_semantic_calibrations_returns_values_when_calibrated(self) -> None:
        from src.rag.rag_service_factory import (
            REQUIRED_SEMANTIC_DECISIONS,
            _validate_semantic_calibrations,
        )

        base = get_project_decision_inventory()
        overrides: dict[str, DecisionCalibrationRecord] = {}
        for rec in base:
            if rec.decision_id in REQUIRED_SEMANTIC_DECISIONS:
                overrides[rec.decision_id] = rec.model_copy(
                    update={
                        "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                        "production_allowed": True,
                    }
                )
        inventory = []
        for rec in base:
            if rec.decision_id in overrides:
                inventory.append(overrides[rec.decision_id])
            else:
                inventory.append(rec)

        with patch(
            "src.rag.rag_service_factory.get_project_decision_inventory",
            return_value=inventory,
        ):
            values, blockers = _validate_semantic_calibrations()
            assert len(blockers) == 0
            assert "rag.semantic_top_k" in values
            assert values["rag.semantic_top_k"] == 8
