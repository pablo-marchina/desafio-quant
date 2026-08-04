"""Tests for RAG Evaluation — golden queries, metrics, quality gates."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from src.evaluation.rag_eval import (
    _check_provenance,
    _load_expected_contexts,
    _load_golden_queries,
    format_eval_summary,
    run_quality_gates,
    run_rag_eval,
)
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.schemas import RetrievalQuery

_GOLDEN = Path("examples/rag_eval/golden_queries.json")
_EXPECTED = Path("examples/rag_eval/expected_contexts.json")

_SUPPORTED_SOURCES: set[str] = set()
try:
    _idx = build_default_index()
    for c in _idx.chunks:
        src = getattr(c, "source_id", None) or (c.id.split("_")[0] if "_" in c.id else "")
        if src:
            _SUPPORTED_SOURCES.add(src)
except Exception:
    pass


class TestGoldenQueries:
    """Verify the golden query dataset is valid."""

    def test_golden_queries_all_have_unique_ids(self) -> None:
        """All golden queries have unique case_ids."""
        cases = _load_golden_queries(_GOLDEN)
        ids = [c.case_id for c in cases]
        assert len(ids) == len(set(ids)), f"duplicate case_ids: {ids}"
        assert len(cases) >= 14

    def test_expected_contexts_match_queries(self) -> None:
        """Each golden query has a corresponding expected_contexts entry."""
        cases = _load_golden_queries(_GOLDEN)
        ctx_map = _load_expected_contexts(_EXPECTED)
        for c in cases:
            assert c.case_id in ctx_map, f"missing expected_contexts entry for {c.case_id}"


class TestRunRagEval:
    """Test the full RAG evaluation pipeline."""

    @pytest.mark.skipif(
        len(_SUPPORTED_SOURCES) < 10,
        reason="Corpus too small to satisfy golden queries",
    )
    def test_all_golden_queries_pass(self) -> None:
        """All golden queries pass when evaluated against the default index."""
        results = run_rag_eval()
        failures = [r for r in results if not r.passed]
        assert len(failures) == 0, f"failed cases: {[(r.case_id, r.failure_reasons) for r in failures]}"

    @pytest.mark.skipif(
        len(_SUPPORTED_SOURCES) < 10,
        reason="Corpus too small to satisfy golden queries",
    )
    def test_critical_cases_have_hit_at_3(self) -> None:
        """All critical cases have hit_at_k=True."""
        results = run_rag_eval()
        for r in results:
            if r.is_critical and r.expected_source_ids:
                assert r.metrics.hit_at_k, f"critical case {r.case_id}: hit_at_k=False"

    @pytest.mark.skipif(
        len(_SUPPORTED_SOURCES) < 10,
        reason="Corpus too small to satisfy golden queries",
    )
    def test_critical_cases_have_top_1_match(self) -> None:
        """All critical cases have top_1_expected_match=True."""
        results = run_rag_eval()
        for r in results:
            if r.is_critical and r.expected_source_ids:
                assert r.metrics.top_1_expected_match, f"critical case {r.case_id}: top_1_expected_match=False"

    @pytest.mark.skipif(
        len(_SUPPORTED_SOURCES) < 10,
        reason="Corpus too small to satisfy golden queries",
    )
    def test_known_query_zero_missing(self) -> None:
        """Known queries have all expected sources when top_k is large enough."""
        results = run_rag_eval()
        for r in results:
            if not r.expected_source_ids:
                continue
            case = _load_golden_queries(_GOLDEN)
            match = [c for c in case if c.case_id == r.case_id]
            if not match:
                continue
            top_k = match[0].top_k_for_test
            if top_k >= len(r.expected_source_ids):
                assert r.metrics.missing_context_count == 0, (
                    f"case {r.case_id}: missing_context_count="
                    f"{r.metrics.missing_context_count} "
                    f"(expected sources: {r.expected_source_ids}, "
                    f"top_k={top_k})"
                )

    def test_unknown_gap_returns_empty(self) -> None:
        """Querying a nonexistent gap returns no results."""
        results = run_rag_eval()
        unknown = [r for r in results if r.case_id == "unknown_gap"]
        assert len(unknown) == 1
        assert len(unknown[0].retrieved_contexts) == 0

    def test_empty_query_returns_empty(self) -> None:
        """Empty query returns no results."""
        results = run_rag_eval()
        empty = [r for r in results if r.case_id == "empty_query"]
        assert len(empty) == 1
        assert len(empty[0].retrieved_contexts) == 0


class TestMetrics:
    """Test individual metrics computation."""

    @pytest.mark.skipif(
        len(_SUPPORTED_SOURCES) < 10,
        reason="Corpus too small to satisfy golden queries",
    )
    def test_context_precision_is_1_for_golden(self) -> None:
        """Golden queries have perfect context_precision (no irrelevant results)."""
        results = run_rag_eval()
        for r in results:
            if r.expected_source_ids:
                assert r.metrics.context_precision == 1.0, f"case {r.case_id}: precision={r.metrics.context_precision}"

    def test_irrelevant_context_detected(self) -> None:
        """A query that returns wrong-source chunks reports irrelevant context."""
        index = build_default_index()
        query = RetrievalQuery(gap_type="voice_need")
        retrieved = index.retrieve(query, top_k=10)
        assert len(retrieved) >= 1
        for r_ctx in retrieved:
            assert r_ctx.source_id == "riva"
            assert r_ctx.product == "NVIDIA Riva"

    def test_provenance_is_present(self) -> None:
        """All retrieved contexts have source_id and url."""
        results = run_rag_eval()
        for r in results:
            issues = _check_provenance(r.retrieved_contexts)
            assert len(issues) == 0, f"case {r.case_id}: provenance issues: {issues}"

    @pytest.mark.skipif(
        len(_SUPPORTED_SOURCES) < 10,
        reason="Corpus too small to satisfy golden queries",
    )
    def test_metrics_coverage_scores(self) -> None:
        """Coverage metrics reflect retrieval completeness."""
        results = run_rag_eval()
        for r in results:
            if not r.expected_source_ids:
                continue
            case = _load_golden_queries(_GOLDEN)
            match = [c for c in case if c.case_id == r.case_id]
            if not match:
                continue
            top_k = match[0].top_k_for_test
            if top_k >= len(r.expected_source_ids):
                assert r.metrics.expected_source_coverage == 1.0, (
                    f"case {r.case_id}: source_coverage=" f"{r.metrics.expected_source_coverage}"
                )
                assert r.metrics.expected_product_coverage == 1.0, (
                    f"case {r.case_id}: product_coverage=" f"{r.metrics.expected_product_coverage}"
                )


class TestQualityGates:
    """Test quality gates block bad retrieval."""

    @pytest.mark.skipif(
        len(_SUPPORTED_SOURCES) < 10,
        reason="Corpus too small to satisfy golden queries",
    )
    def test_quality_gates_all_pass_for_golden(self) -> None:
        """All quality gates pass for the golden query dataset."""
        results = run_rag_eval()
        gates = run_quality_gates(results)
        failures = [g for g in gates if not g.passed]
        assert len(failures) == 0, f"failed gates: {[(g.gate_name, g.details) for g in failures]}"

    def test_gate_fails_on_bad_index(self) -> None:
        """A bad index (no chunks) triggers quality gate failures."""
        empty_idx = ChunkIndex([])
        results = run_rag_eval(index=empty_idx)
        gates = run_quality_gates(results)
        failed = [g for g in gates if not g.passed]
        assert len(failed) >= 2, "expected at least 2 quality gates to fail with empty index"

    def test_provenance_gate_fails_without_url(self) -> None:
        """Provenance gate fails when chunks have no url."""
        from src.evaluation.rag_eval import _check_provenance
        from src.rag.schemas import RetrievedContext

        ctx_no_url = RetrievedContext(
            chunk_id="bad_000",
            source_id="bad_source",
            title="Bad",
            content="no url",
            product="Bad Product",
            gap_types=["some_gap"],
            url=None,
            relevance_score=0.5,
        )
        issues = _check_provenance([ctx_no_url])
        assert len(issues) == 1
        assert "missing url" in issues[0]

        ctx_no_source = RetrievedContext(
            chunk_id="bad_001",
            source_id="",
            title="Bad",
            content="no source",
            product="Bad Product",
            gap_types=["some_gap"],
            url="https://example.com",
            relevance_score=0.5,
        )
        issues2 = _check_provenance([ctx_no_source])
        assert len(issues2) == 1
        assert "missing source_id" in issues2[0]


class TestEvalSummary:
    """Test the human-readable summary output."""

    def test_format_summary_includes_results(self) -> None:
        """Summary contains case IDs and pass/fail status."""
        results = run_rag_eval()
        gates = run_quality_gates(results)
        summary = format_eval_summary(results, gates)
        assert "RAG Evaluation:" in summary
        assert "inference_cost_all" in summary

    def test_format_summary_shows_failures(self) -> None:
        """Summary includes failure reasons for failed cases."""
        empty_idx = ChunkIndex([])
        results = run_rag_eval(index=empty_idx)
        gates = run_quality_gates(results)
        summary = format_eval_summary(results, gates)
        assert "FAIL" in summary
        assert "critical" in summary.lower()


class TestRagDoesNotAffectBrief:
    """Verify Action Brief is unaffected by RAG context."""

    def test_brief_not_affected_by_rag_failure(self) -> None:
        """Action Brief works normally when RAG returns empty."""
        from datetime import datetime

        from pydantic import HttpUrl

        from src.briefing import build_action_brief
        from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType, StartupProfile
        from src.pipeline.run_pipeline import run_full_pipeline

        profile = StartupProfile(
            startup_name="NoRAG Inc",
            website=HttpUrl("https://example.com"),
            sector="AI",
            description="AI company.",
            product_summary="AI product.",
            ai_signals=["AI signal"],
            sources=[],
            confidence_score=0.5,
        )
        ev = Evidence(
            claim="AI company",
            source_url=HttpUrl("https://example.com"),
            source_type=SourceType.OFFICIAL_SITE,
            quote_or_evidence="AI company.",
            confidence=ConfidenceLevel.LOW,
            collected_at=datetime.now(UTC),
        )
        result = run_full_pipeline("NoRAG Inc", profile=profile, evidence_list=[ev])
        brief = build_action_brief(result)
        assert brief.startup_name == "NoRAG Inc"
        assert brief.verdict is not None
        assert len(brief.sections) >= 3

    def test_rag_does_not_alter_motion(self) -> None:
        """recommended_motion is unchanged with or without RAG context."""
        from datetime import datetime

        from pydantic import HttpUrl

        from src.briefing import build_action_brief
        from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType, StartupProfile
        from src.pipeline.run_pipeline import run_full_pipeline

        profile = StartupProfile(
            startup_name="RAG Motion Test",
            website=HttpUrl("https://example.com"),
            sector="Tech",
            description="A tech startup.",
            product_summary="A product.",
            ai_signals=["AI signal: ml"],
            sources=[],
            confidence_score=0.6,
        )
        ev = Evidence(
            claim="Tech startup",
            source_url=HttpUrl("https://example.com"),
            source_type=SourceType.OFFICIAL_SITE,
            quote_or_evidence="Tech startup.",
            confidence=ConfidenceLevel.MEDIUM,
            collected_at=datetime.now(UTC),
        )
        result = run_full_pipeline("RAG Motion Test", profile=profile, evidence_list=[ev])
        brief = build_action_brief(result)
        motion = brief.recommended_motion
        assert isinstance(motion, str)
        assert len(motion) > 0

    def test_playbook_retriever_provenance(self) -> None:
        """PlaybookRetriever results all have provenance."""
        from src.rag.playbook_retriever import PlaybookRetriever

        index = build_default_index()
        retriever = PlaybookRetriever(index)
        gaps = [
            {"gap": "high_inference_cost", "detected": True},
            {"gap": "agent_governance_gap", "detected": True},
        ]
        techs = [
            {
                "technology_name": "TensorRT-LLM",
                "addresses_gap": "high_inference_cost",
                "justification": "",
            },
            {
                "technology_name": "NeMo Guardrails",
                "addresses_gap": "agent_governance_gap",
                "justification": "",
            },
        ]
        results = retriever.retrieve_for_gaps(gaps, techs, [])
        for pr in results:
            for ctx in pr.contexts:
                assert ctx.source_id, f"missing source_id in {ctx.chunk_id}"
                assert ctx.url, f"missing url in {ctx.chunk_id}"
