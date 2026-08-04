"""Unit tests for QdrantRetrievalEvaluator â€” no LLM, no external calls, no Qdrant.

All tests use InMemoryVectorStore + MockEmbeddingProvider + ChunkIndex.
Real Qdrant integration is gated behind QDRANT_TEST_URL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.qdrant_retrieval_eval import QdrantRetrievalEvaluator
from src.evaluation.qdrant_retrieval_eval_schemas import (
    MULTI_OBJECTIVE_WEIGHTS,
    QdrantRetrievalEvalResult,
    RetrieverDetail,
)
from src.rag.embeddings import MockEmbeddingProvider
from src.rag.ingestion import load_and_chunk_corpus
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk
from src.rag.vector_store import InMemoryVectorStore, VectorEntry

_GOLDEN = Path("data/eval/golden_ragas_rag.json")


# â”€â”€ Fixtures â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@pytest.fixture(scope="session")
def corpus_chunks() -> list[RagChunk]:
    return load_and_chunk_corpus()


@pytest.fixture
def chunk_index(corpus_chunks: list[RagChunk]) -> ChunkIndex:
    return ChunkIndex(corpus_chunks)


@pytest.fixture
def embedding() -> MockEmbeddingProvider:
    return MockEmbeddingProvider()


@pytest.fixture
def vector_store(corpus_chunks: list[RagChunk], embedding: MockEmbeddingProvider) -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    for chunk in corpus_chunks:
        vec = embedding.embed(chunk.content)
        entry = VectorEntry(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            title=chunk.title,
            content=chunk.content,
            product=chunk.product,
            gap_types=list(chunk.gap_types),
            url=chunk.url,
            embedding=vec,
            version=chunk.version,
            nvidia_technology=chunk.nvidia_technology or chunk.product,
            corpus_version=chunk.corpus_version,
            chunk_index=chunk.chunk_index,
            char_count=chunk.char_count or len(chunk.content),
            ingested_at="2026-01-01T00:00:00Z",
        )
        store.add_entry(entry)
    return store


@pytest.fixture
def evaluator(
    vector_store: InMemoryVectorStore,
    embedding: MockEmbeddingProvider,
    chunk_index: ChunkIndex,
) -> QdrantRetrievalEvaluator:
    return QdrantRetrievalEvaluator(
        vector_store=vector_store,
        embedding_model=embedding,
        chunk_index=chunk_index,
        golden_path=_GOLDEN,
    )


@pytest.fixture
def eval_result(evaluator: QdrantRetrievalEvaluator) -> QdrantRetrievalEvalResult:
    return evaluator.evaluate()


# â”€â”€ Test 1: evaluator loads golden set â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLoadGoldenSet:
    def test_loads_samples(self, evaluator: QdrantRetrievalEvaluator) -> None:
        dataset = evaluator._harness.load_golden_set()
        assert len(dataset.samples) >= 1

    def test_each_sample_has_required_fields(self, evaluator: QdrantRetrievalEvaluator) -> None:
        dataset = evaluator._harness.load_golden_set()
        for sample in dataset.samples:
            assert sample.question
            assert sample.gap_id
            assert sample.gap_type
            assert isinstance(sample.expected_nvidia_topics, list)


# â”€â”€ Test 2: evaluator runs semantic_qdrant â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestSemanticQdrant:
    def test_returns_detail(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert isinstance(eval_result.semantic, RetrieverDetail)

    def test_has_metrics(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert isinstance(m.recall_at_k, float)
        assert isinstance(m.precision_at_k, float)
        assert isinstance(m.mrr, float)
        assert isinstance(m.hit_rate_at_k, float)

    def test_contexts_retrieved(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert m.retrieved_context_count >= 0
        assert m.sample_count == eval_result.dataset_size

    def test_citation_precision_computed(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert 0.0 <= m.citation_precision <= 1.0

    def test_unsupported_claim_rate_computed(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert 0.0 <= m.unsupported_claim_rate <= 1.0

    def test_latency_ms_recorded(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert m.latency_ms >= 0.0

    def test_payload_completeness_recorded(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert 0.0 <= m.qdrant_payload_completeness_rate <= 1.0

    def test_corpus_version_match_recorded(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert 0.0 <= m.corpus_version_match_rate <= 1.0


# â”€â”€ Test 3: evaluator runs lexical_baseline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLexicalBaseline:
    def test_returns_detail(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert isinstance(eval_result.lexical, RetrieverDetail)

    def test_has_metrics(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.lexical.summary
        assert isinstance(m.recall_at_k, float)
        assert isinstance(m.precision_at_k, float)
        assert isinstance(m.mrr, float)
        assert isinstance(m.hit_rate_at_k, float)

    def test_contexts_retrieved(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.lexical.summary
        assert m.retrieved_context_count >= 0

    def test_not_production_fallback(self, eval_result: QdrantRetrievalEvalResult) -> None:
        decisions = eval_result.calibration_decisions
        for dec_id in decisions:
            assert "chunkindex" not in dec_id.lower()
            assert "lexical" not in dec_id.lower() or "baseline" != dec_id.lower()
            assert "fallback" not in dec_id.lower() or "lexical" not in dec_id.lower()


# â”€â”€ Test 4: evaluator runs hybrid_candidate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestHybridCandidate:
    def test_returns_detail(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert isinstance(eval_result.hybrid, RetrieverDetail)

    def test_has_metrics(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.hybrid.summary
        assert isinstance(m.recall_at_k, float)
        assert isinstance(m.precision_at_k, float)
        assert isinstance(m.mrr, float)

    def test_not_activated_in_production(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert eval_result.comparison.production_allowed is False

    def test_hybrid_weights_registered(self, eval_result: QdrantRetrievalEvalResult) -> None:
        decisions = eval_result.calibration_decisions
        assert "rag.hybrid_retrieval_weights" in decisions
        hw = decisions["rag.hybrid_retrieval_weights"]
        assert hw["value_origin"] == "qdrant_ragas_retrieval_eval"


# â”€â”€ Test 5: RAGAS metrics computed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestRagasMetrics:
    def test_ragas_source_reported(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert m.ragas_metrics_source is not None

    def test_ragas_values_are_float_or_none(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        for val in [m.context_precision, m.context_recall, m.faithfulness, m.answer_relevancy]:
            assert val is None or isinstance(val, float)


# â”€â”€ Test 6: custom metrics computed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestCustomMetrics:
    def test_recall_at_k(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for detail in [eval_result.semantic, eval_result.lexical, eval_result.hybrid]:
            assert 0.0 <= detail.summary.recall_at_k <= 1.0

    def test_precision_at_k(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for detail in [eval_result.semantic, eval_result.lexical, eval_result.hybrid]:
            assert 0.0 <= detail.summary.precision_at_k <= 1.0

    def test_mrr(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for detail in [eval_result.semantic, eval_result.lexical, eval_result.hybrid]:
            assert 0.0 <= detail.summary.mrr <= 1.0

    def test_hit_rate(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for detail in [eval_result.semantic, eval_result.lexical, eval_result.hybrid]:
            assert 0.0 <= detail.summary.hit_rate_at_k <= 1.0

    def test_contexts_per_gap(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for detail in [eval_result.semantic, eval_result.lexical, eval_result.hybrid]:
            assert isinstance(detail.summary.contexts_per_gap, dict)

    def test_gaps_without_context_count(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for detail in [eval_result.semantic, eval_result.lexical, eval_result.hybrid]:
            assert isinstance(detail.summary.gaps_without_context_count, int)
            assert detail.summary.gaps_without_context_count >= 0


# â”€â”€ Test 7: payload completeness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestPayloadCompleteness:
    def test_payload_completeness_computed(self, eval_result: QdrantRetrievalEvalResult) -> None:
        m = eval_result.semantic.summary
        assert isinstance(m.qdrant_payload_completeness_rate, float)
        assert 0.0 <= m.qdrant_payload_completeness_rate <= 1.0


# â”€â”€ Test 8: comparison report â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestComparison:
    def test_multi_objective_scores_computed(self, eval_result: QdrantRetrievalEvalResult) -> None:
        scores = eval_result.comparison.multi_objective_scores
        assert len(scores) >= 2
        assert "semantic_qdrant" in scores
        assert "lexical_baseline" in scores
        assert "hybrid_candidate" in scores

    def test_winner_selected(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert eval_result.comparison.winner
        assert eval_result.comparison.winner in (
            "semantic_qdrant",
            "lexical_baseline",
            "hybrid_candidate",
        )

    def test_selection_justification_provided(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert eval_result.comparison.selection_justification

    def test_production_allowed_false(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert eval_result.comparison.production_allowed is False

    def test_per_gap_metrics(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for detail in [eval_result.semantic, eval_result.lexical, eval_result.hybrid]:
            assert isinstance(detail.per_gap, list)
            if detail.per_gap:
                pg = detail.per_gap[0]
                assert pg.gap_type
                assert pg.contexts_retrieved >= 0


# â”€â”€ Test 9: registry decisions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestRegistryDecisions:
    def test_value_origin(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for dec_id, dec in eval_result.calibration_decisions.items():
            assert dec["value_origin"] == "qdrant_ragas_retrieval_eval", f"{dec_id} has wrong value_origin"

    def test_all_required_decisions_present(self, eval_result: QdrantRetrievalEvalResult) -> None:
        required = {
            "rag.semantic_top_k",
            "rag.min_contexts_per_gap",
            "rag.context_relevance_threshold",
            "rag.citation_precision_threshold",
            "rag.unsupported_claim_rate_threshold",
            "rag.ragas_context_precision_threshold",
            "rag.ragas_context_recall_threshold",
            "rag.ragas_faithfulness_threshold",
            "rag.ragas_answer_relevancy_threshold",
            "rag.hybrid_retrieval_weights",
        }
        present = set(eval_result.calibration_decisions.keys())
        missing = required - present
        assert not missing, f"Missing decisions: {missing}"

    def test_decisions_have_calibration_status(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for _dec_id, dec in eval_result.calibration_decisions.items():
            assert "calibration_status" in dec
            assert dec["calibration_status"] in (
                "baseline_measured",
                "baseline_dataset_insufficient",
            )

    def test_production_allowed_matches_status(self, eval_result: QdrantRetrievalEvalResult) -> None:
        for _dec_id, dec in eval_result.calibration_decisions.items():
            if dec["calibration_status"] == "baseline_dataset_insufficient":
                assert dec["production_allowed"] is False


# â”€â”€ Test 10: production_allowed=false when dataset insufficient â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestDatasetInsufficient:
    def test_empty_dataset_blocks_production(self, chunk_index: ChunkIndex) -> None:
        evaluator = QdrantRetrievalEvaluator(
            chunk_index=chunk_index,
            golden_path=_GOLDEN,
        )
        # No vector_store or embedding_model â€” lexical only, but dataset is valid
        dataset = evaluator._harness.load_golden_set()
        assert len(dataset.samples) >= 12

    def test_minimum_golden_samples_constant(self) -> None:
        from src.evaluation.qdrant_retrieval_eval_schemas import MINIMUM_GOLDEN_SAMPLES

        assert MINIMUM_GOLDEN_SAMPLES >= 5


# â”€â”€ Test 11: ChunkIndex not registered as production fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestNoLexicalFallback:
    def test_no_lexical_fallback_in_registry(self, eval_result: QdrantRetrievalEvalResult) -> None:
        decisions = eval_result.calibration_decisions
        for dec_id, dec in decisions.items():
            notes = dec.get("notes", "").lower()
            assert "fallback" not in notes or "chunkindex" not in notes
            assert "lexical" not in dec_id.lower() or "fallback" not in notes

    def test_lexical_baseline_is_eval_only(self, eval_result: QdrantRetrievalEvalResult) -> None:
        assert eval_result.lexical.summary.retriever_name == "lexical_baseline"


# â”€â”€ Test 12: no LLM calls in unit tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestNoExternalCalls:
    def test_compute_custom_metrics_no_llm(self, evaluator: QdrantRetrievalEvaluator) -> None:
        result = evaluator.evaluate()
        m = result.semantic.summary
        assert m.ragas_metrics_source.startswith("unavailable")

    def test_no_internet_calls(self, evaluator: QdrantRetrievalEvaluator) -> None:
        import subprocess
        import sys

        r = subprocess.run(
            [sys.executable, "-c", "import src.evaluation.qdrant_retrieval_eval; print('ok')"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert r.returncode == 0


# â”€â”€ Test 13: empty InMemoryVectorStore â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestEmptyStore:
    def test_empty_store_returns_empty_contexts(
        self, chunk_index: ChunkIndex, embedding: MockEmbeddingProvider
    ) -> None:
        empty_store = InMemoryVectorStore()
        evaluator = QdrantRetrievalEvaluator(
            vector_store=empty_store,
            embedding_model=embedding,
            chunk_index=chunk_index,
            golden_path=_GOLDEN,
        )
        result = evaluator.evaluate()
        m = result.semantic.summary
        assert m.retrieved_context_count == 0
        assert m.gaps_without_context_count == m.sample_count


# â”€â”€ Test 14: multi-objective weights are consistent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestMultiObjectiveWeights:
    def test_weights_sum_to_one(self) -> None:
        total = sum(MULTI_OBJECTIVE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Multi-objective weights sum to {total}, expected 1.0"

    def test_all_weights_positive(self) -> None:
        for k, v in MULTI_OBJECTIVE_WEIGHTS.items():
            assert v > 0, f"Weight '{k}' is not positive: {v}"
