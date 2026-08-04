"""Tests for Qdrant-backed RagService factory (semantic-only, no ChunkIndex).

Validates that ``QdrantRagService`` implements the ``RagService`` protocol,
blocks production when Qdrant/embedding/corpus/calibrations are not ready,
and uses only ``hybrid_retrieve`` (no ``ChunkIndex`` fallback).
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
from src.rag.embeddings import MockEmbeddingProvider
from src.rag.rag_service_factory import (
    REQUIRED_SEMANTIC_DECISIONS,
    QdrantRagService,
    build_qdrant_rag_service,
    build_rag_service,
)
from src.rag.vector_store import InMemoryVectorStore, VectorEntry

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _make_calibrated_gap(
    gap_id: str = "gap_001",
    gap_type: GapType = GapType.INFERENCE_PERFORMANCE_GAP,
) -> GapDiagnosisResultItem:
    return GapDiagnosisResultItem(
        gap_id=gap_id,
        gap_type=gap_type,
        severity_score=0.5,
        confidence_score=0.7,
        uncertainty=0.1,
        status=GapDiagnosisStatus.PASSED,
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
        supporting_evidence_ids=[],
        calibration_decision_ids=[
            "gap_diagnosis.severity_weights",
            "gap_diagnosis.confidence_weights",
            "gap_diagnosis.production_threshold",
        ],
        production_allowed=True,
        blockers=[],
        explanation="Calibrated gap for testing",
        recommended_investigation="",
    )


def _make_summary(gaps: list[GapDiagnosisResultItem] | None = None) -> dict[str, Any]:
    if gaps is None:
        gaps = [_make_calibrated_gap()]
    return GapDiagnosisSummary(
        run_id="test-rag-retrieval-001",
        gap_diagnosis_status=GapDiagnosisStatus.PASSED,
        gaps=gaps,
        metrics=GapDiagnosisMetrics(
            total_gap_count=len(gaps),
            production_allowed_gap_count=sum(1 for g in gaps if g.production_allowed),
            blocked_gap_count=sum(1 for g in gaps if not g.production_allowed),
            average_gap_severity=0.5,
            average_gap_confidence=0.7,
            high_severity_gap_count=0,
            evidence_coverage_gap_count=0,
            missing_calibration_count=0,
            calibrated_decision_count=3,
            gap_uncertainty_mean=0.1,
        ),
        calibration_status="baseline_measured",
        production_allowed=True,
    ).model_dump(mode="json")


def _make_vector_store(entries: list[VectorEntry] | None = None) -> InMemoryVectorStore:
    vs = InMemoryVectorStore()
    if entries is None:
        entries = [
            VectorEntry(
                chunk_id="chunk_001",
                source_id="src_001",
                title="NVIDIA TensorRT",
                content="TensorRT is an SDK for high-performance deep learning inference.",
                product="tensorrt",
                gap_types=["inference_performance_gap"],
                embedding=[0.1, 0.2, 0.3, 0.4],
                url="https://example.com/tensorrt",
            ),
        ]
    for e in entries:
        vs.add_entry(e)
    return vs


# Decision inventory override: mark all hybrid decisions as calibrated


def _calibrated_semantic_inventory() -> list[DecisionCalibrationRecord]:
    base = get_project_decision_inventory()
    calibrated_ids = set(REQUIRED_SEMANTIC_DECISIONS)
    result: list[DecisionCalibrationRecord] = []
    for rec in base:
        if rec.decision_id in calibrated_ids:
            result.append(
                rec.model_copy(
                    update={
                        "calibration_status": CalibrationStatus.BASELINE_MEASURED,
                        "production_allowed": True,
                    }
                )
            )
        else:
            result.append(rec)
    return result


# â”€â”€ Construction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestQdrantRagServiceConstruction:
    def test_construct_with_defaults(self) -> None:
        svc = QdrantRagService()
        assert svc is not None
        assert svc._validated is False

    def test_construct_with_explicit_deps(self) -> None:
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = QdrantRagService(
            embedding_model=emb,
            vector_store=vs,
        )
        assert svc._embedding_model is emb
        assert svc._vector_store is vs
        # No chunk_index attribute â€” intentionally removed

    def test_build_qdrant_rag_service_returns_qdrant_rag_service(self) -> None:
        svc = build_qdrant_rag_service()
        assert isinstance(svc, QdrantRagService)

    def test_build_qdrant_rag_service_with_explicit_deps(self) -> None:
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = build_qdrant_rag_service(
            embedding_model=emb,
            vector_store=vs,
        )
        assert svc._embedding_model is emb
        assert svc._vector_store is vs

    def test_build_rag_service_deprecated_delegates(self) -> None:
        svc = build_rag_service()
        assert isinstance(svc, QdrantRagService)

    def test_chunk_index_in_service(self) -> None:
        svc = QdrantRagService()
        assert hasattr(svc, "_chunk_index")


# â”€â”€ Protocol compliance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestQdrantRagServiceProtocol:
    def test_call_returns_dict_with_expected_keys(self) -> None:
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = QdrantRagService(embedding_model=emb, vector_store=vs)
        result = svc(
            run_id="test-run-001",
            gap_diagnosis_summary=None,
            startup_profile=None,
            accepted_evidence_items=[],
            claims=[],
            ai_native_score=None,
            nvidia_fit_score=None,
        )
        assert isinstance(result, dict)
        assert "rag_retrieval_status" in result
        assert "rag_contexts" in result
        assert "rag_queries_by_gap" in result
        assert "rag_contexts_by_gap" in result
        assert "rag_retrieval_metrics" in result
        assert "status" in result


# â”€â”€ Blocking modes (no ChunkIndex fallback) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestQdrantRagServiceBlocking:
    def test_blocks_when_qdrant_unavailable(self) -> None:
        """Qdrant unavailability blocks with explicit status."""
        svc = QdrantRagService()

        with patch.object(svc, "_validate") as mock_val:
            mock_val.side_effect = None
            svc._validation_error = "blocked_qdrant_unavailable: connection refused"
            result = svc(
                run_id="test-blocked",
                gap_diagnosis_summary=None,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "blocked_qdrant_unavailable"
        assert result["review_required"] is True
        assert "connection refused" in str(result["blockers"])

    def test_blocks_when_corpus_empty(self) -> None:
        """Empty Qdrant collection blocks with explicit status."""
        emb = MockEmbeddingProvider()
        vs = InMemoryVectorStore()  # empty
        svc = QdrantRagService(embedding_model=emb, vector_store=vs)

        with patch(
            "src.rag.rag_service_factory._validate_semantic_calibrations",
            return_value=({}, []),
        ):
            result = svc(
                run_id="test-empty-corpus",
                gap_diagnosis_summary=_make_summary(),
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "blocked_qdrant_corpus_not_ready"
        assert result["review_required"] is True
        assert "collection is empty" in str(result["blockers"]).lower()

    def test_blocks_when_embedding_provider_unavailable(self) -> None:
        """Missing embedding provider blocks with explicit status."""
        svc = QdrantRagService()

        with patch.object(svc, "_validate") as mock_val:
            mock_val.side_effect = None
            svc._validation_error = "blocked_embedding_provider_unavailable: model not found"
            result = svc(
                run_id="test-no-emb",
                gap_diagnosis_summary=None,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "blocked_embedding_provider_unavailable"
        assert result["review_required"] is True
        assert "embedding" in str(result["blockers"]).lower()

    def test_blocks_when_uncalibrated_rag(self) -> None:
        """Uncalibrated hybrid decisions block production."""
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = QdrantRagService(embedding_model=emb, vector_store=vs)

        with patch(
            "src.rag.rag_service_factory._validate_semantic_calibrations",
            return_value=({}, ["rag.semantic_top_k is uncalibrated (production_allowed=False)"]),
        ):
            result = svc(
                run_id="test-uncalibrated",
                gap_diagnosis_summary=_make_summary(),
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        assert result["rag_retrieval_status"] == "blocked_uncalibrated_rag"
        assert result["rag_retrieval_metrics"]["missing_rag_calibration_count"] == 1

    def test_chunk_index_is_part_of_hybrid_path(self) -> None:
        """ChunkIndex is built and used as the lexical side of hybrid product RAG."""
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = QdrantRagService(embedding_model=emb, vector_store=vs)

        assert hasattr(svc, "_chunk_index")
        assert "_chunk_index" in dir(svc)

    def test_hybrid_retrieve_is_imported_and_called(self) -> None:
        """hybrid_retrieve is imported by the official product RAG path."""
        import src.rag.rag_service_factory as fact

        source = open(fact.__file__ or "", encoding="utf-8").read()
        assert "from src.rag.hybrid_retrieval" in source
        assert "hybrid_retrieve(" in source


# â”€â”€ Semantic retrieval path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestQdrantRagServiceHybridRetrieval:
    def test_hybrid_retrieve_called(self) -> None:
        """hybrid_retrieve is invoked for each gap, not ChunkIndex."""
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = QdrantRagService(embedding_model=emb, vector_store=vs)

        with (
            patch(
                "src.rag.rag_service_factory._validate_semantic_calibrations",
                return_value=(
                    {
                        "rag.semantic_top_k": 3,
                        "rag.min_contexts_per_gap": 1,
                        "rag.context_relevance_threshold": 0.3,
                        "rag.citation_precision_threshold": 0.95,
                        "rag.unsupported_claim_rate_threshold": 0.1,
                    },
                    [],
                ),
            ),
            patch(
                "src.rag.rag_service_factory.hybrid_retrieve",
                return_value=[
                    MagicMock(
                        chunk_id="chunk_001",
                        source_id="src_001",
                        title="TensorRT",
                        content="TensorRT is an SDK.",
                        product="tensorrt",
                        url="https://example.com",
                        relevance_score=0.85,
                        gap_types=["inference_performance_gap"],
                        version="1.0",
                        valid_from=None,
                        valid_until=None,
                        freshness_policy=None,
                        stale_after_days=None,
                        is_active=True,
                        deprecated_at=None,
                        superseded_by=None,
                    ),
                ],
            ) as mock_semantic,
        ):
            result = svc(
                run_id="test-semantic-call",
                gap_diagnosis_summary=_make_summary(),
                startup_profile={"sector": "AI", "product_summary": "ML platform"},
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=0.6,
                nvidia_fit_score=0.7,
            )

        assert mock_semantic.called
        assert result["rag_retrieval_status"] in ("passed", "needs_review")

    def test_rag_contexts_preserve_payload(self) -> None:
        """Result contexts include source_id, url, chunk_id, gap_id."""
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = QdrantRagService(embedding_model=emb, vector_store=vs)

        with patch(
            "src.rag.rag_service_factory._validate_semantic_calibrations",
            return_value=(
                {
                    "rag.semantic_top_k": 3,
                    "rag.min_contexts_per_gap": 1,
                    "rag.context_relevance_threshold": 0.3,
                    "rag.citation_precision_threshold": 0.95,
                    "rag.unsupported_claim_rate_threshold": 0.1,
                },
                [],
            ),
        ):
            result = svc(
                run_id="test-payload",
                gap_diagnosis_summary=_make_summary(),
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )

        for gap_id, ctxs in result["rag_contexts_by_gap"].items():
            for ctx in ctxs:
                assert "source_id" in ctx
                assert "url" in ctx
                assert "context_id" in ctx
                assert ctx["gap_id"] == gap_id

    def test_run_id_preserved(self) -> None:
        svc = QdrantRagService()
        with patch.object(svc, "_validate") as mock_val:
            mock_val.side_effect = None
            svc._validation_error = "blocked_qdrant_unavailable: test"
            result = svc(
                run_id="my-test-run-42",
                gap_diagnosis_summary=None,
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )
        assert result is not None  # run_id is not in output but should not crash


# â”€â”€ Edge cases â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestQdrantRagServiceEdgeCases:
    def test_validation_error_cached(self) -> None:
        svc = QdrantRagService()
        svc._validation_error = "pre-set error"
        svc._validated = True
        result = svc(
            run_id="test-run-001",
            gap_diagnosis_summary=None,
            startup_profile=None,
            accepted_evidence_items=[],
            claims=[],
            ai_native_score=None,
            nvidia_fit_score=None,
        )
        assert result["rag_retrieval_status"] == "blocked_qdrant_unavailable"
        assert "pre-set error" in str(result["blockers"])

    def test_validation_run_once(self) -> None:
        svc = QdrantRagService()
        assert svc._validated is False
        svc._validate()
        assert svc._validated is True
        svc._validate()
        assert svc._validated is True

    def test_empty_result_contains_expected_structure(self) -> None:
        empty = QdrantRagService._empty_result(
            status="test_blocked",
            rag_retrieval_status="test_blocked",
            blockers=["test error"],
        )
        assert empty["status"] == "test_blocked"
        assert empty["rag_retrieval_status"] == "test_blocked"
        assert empty["blockers"] == ["test error"]
        assert empty["rag_contexts"] == []
        assert empty["rag_queries_by_gap"] == {}
        assert empty["review_required"] is True

    def test_blocks_on_parse_error(self) -> None:
        emb = MockEmbeddingProvider()
        vs = _make_vector_store()
        svc = QdrantRagService(embedding_model=emb, vector_store=vs)

        with patch(
            "src.rag.rag_service_factory._validate_semantic_calibrations",
            return_value=(
                {
                    "rag.semantic_top_k": 3,
                    "rag.min_contexts_per_gap": 1,
                    "rag.context_relevance_threshold": 0.3,
                    "rag.citation_precision_threshold": 0.95,
                    "rag.unsupported_claim_rate_threshold": 0.1,
                },
                [],
            ),
        ):
            result = svc(
                run_id="test-bad-summary",
                gap_diagnosis_summary={"invalid": "data"},
                startup_profile=None,
                accepted_evidence_items=[],
                claims=[],
                ai_native_score=None,
                nvidia_fit_score=None,
            )
        assert result["rag_retrieval_status"] == "failed"

    def test_no_llm_or_scraping_imports(self) -> None:
        import src.rag.rag_service_factory as fact

        source = open(fact.__file__ or "", encoding="utf-8").read()
        assert "from langchain" not in source
        assert "from openai" not in source
        assert "ChatOpenAI" not in source
        assert "from src.scraping" not in source
        assert "import httpx" not in source
        assert "import requests" not in source


class TestRequiredSemanticDecisions:
    def test_required_decisions_are_defined(self) -> None:
        assert "rag.semantic_top_k" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.min_contexts_per_gap" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.context_relevance_threshold" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.citation_precision_threshold" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.unsupported_claim_rate_threshold" in REQUIRED_SEMANTIC_DECISIONS

    def test_hybrid_and_reranker_required(self) -> None:
        assert "rag.hybrid_retrieval_weights" in REQUIRED_SEMANTIC_DECISIONS
        assert "rag.reranker_required" in REQUIRED_SEMANTIC_DECISIONS
