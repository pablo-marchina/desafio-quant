"""End-to-end golden evaluation tests for the full pipeline.

Each test loads a golden case from examples/golden/, runs the pipeline,
builds the Action Brief, and asserts expected outputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.briefing.action_brief import build_action_brief
from src.briefing.markdown_renderer import render_action_brief_markdown
from src.rag.embeddings import MockEmbeddingProvider
from src.rag.retrieval import build_default_index
from src.rag.vector_store import InMemoryVectorStore
from tests.evals.helpers import (
    GoldenCase,
    assert_action_brief_sections,
    assert_confidence_coherent,
    assert_expected_gaps,
    assert_expected_motion,
    assert_missing_evidence_propagates,
    assert_no_strong_rec_without_evidence,
    assert_no_tech_without_gap,
    assert_pipeline_contract,
    assert_rag_context_not_in_evidence_used,
    assert_rag_does_not_alter_motion,
    load_golden_case,
    run_pipeline_on_case,
    run_pipeline_with_rag,
)

GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "golden"


def _load(case_id: str) -> GoldenCase:
    return load_golden_case(GOLDEN_DIR / f"{case_id}.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chunk_index():
    return build_default_index()


@pytest.fixture(scope="module")
def embedding_model():
    return MockEmbeddingProvider()


@pytest.fixture(scope="module")
def vector_store():
    return InMemoryVectorStore()


# ---------------------------------------------------------------------------
# Golden case tests
# ---------------------------------------------------------------------------


class TestGoldenHighFit:
    CASE = _load("startup_high_fit")

    def test_pipeline_contract(self):
        result = run_pipeline_on_case(self.CASE)
        assert_pipeline_contract(result)

    def test_expected_motion(self):
        result = run_pipeline_on_case(self.CASE)
        assert_expected_motion(result, self.CASE.expected.get("motion_in", []))

    def test_min_score(self):
        result = run_pipeline_on_case(self.CASE)
        assert result.final_priority_score >= self.CASE.expected.get("min_score", 0)

    def test_expected_gaps(self):
        result = run_pipeline_on_case(self.CASE)
        assert_expected_gaps(result, self.CASE.expected.get("expected_gaps", []))

    def test_no_tech_without_gap(self):
        result = run_pipeline_on_case(self.CASE)
        assert_no_tech_without_gap(result)

    def test_missing_evidence_propagates(self):
        result = run_pipeline_on_case(self.CASE)
        assert_missing_evidence_propagates(result)

    def test_confidence_coherent(self):
        result = run_pipeline_on_case(self.CASE)
        assert_confidence_coherent(result)

    def test_action_brief_sections(self):
        result = run_pipeline_on_case(self.CASE)
        brief = build_action_brief(result)
        assert_action_brief_sections(brief, self.CASE.expected.get("brief_min_sections", 3))

    def test_action_brief_markdown(self):
        result = run_pipeline_on_case(self.CASE)
        brief = build_action_brief(result)
        md = render_action_brief_markdown(brief)
        assert len(md) > 100
        assert "# Startup Action Brief:" in md
        assert "## Executive Summary" in md

    def test_no_strong_rec_without_evidence(self):
        result = run_pipeline_on_case(self.CASE)
        assert_no_strong_rec_without_evidence(result)


class TestGoldenWeakEvidence:
    CASE = _load("startup_weak_evidence")

    def test_expected_motion(self):
        result = run_pipeline_on_case(self.CASE)
        assert_expected_motion(result, self.CASE.expected.get("motion_in", []))
        assert result.recommended_motion == "not_recommended"

    def test_max_score(self):
        result = run_pipeline_on_case(self.CASE)
        max_score = self.CASE.expected.get("max_score", 100)
        assert result.final_priority_score <= max_score

    def test_no_approach_now(self):
        result = run_pipeline_on_case(self.CASE)
        assert_no_strong_rec_without_evidence(result)

    def test_pipeline_contract(self):
        result = run_pipeline_on_case(self.CASE)
        assert_pipeline_contract(result)


class TestGoldenNonAi:
    CASE = _load("startup_non_ai")

    def test_expected_motion(self):
        result = run_pipeline_on_case(self.CASE)
        assert result.recommended_motion == "not_recommended"

    def test_zero_recommendations(self):
        result = run_pipeline_on_case(self.CASE)
        assert result.recommendation is not None
        detected = [r for r in result.recommendation.recommendations if r.detected]
        assert len(detected) == 0, f"Expected zero detected recommendations, " f"got {len(detected)}"

    def test_no_tech_without_gap(self):
        result = run_pipeline_on_case(self.CASE)
        assert_no_tech_without_gap(result)

    def test_max_score(self):
        result = run_pipeline_on_case(self.CASE)
        assert result.final_priority_score <= self.CASE.expected.get("max_score", 100)


class TestGoldenNoRagContext:
    CASE = _load("startup_no_rag_context")

    def test_pipeline_contract(self):
        result = run_pipeline_on_case(self.CASE)
        assert_pipeline_contract(result)

    def test_expected_gaps(self):
        result = run_pipeline_on_case(self.CASE)
        expected = self.CASE.expected.get("expected_gaps", [])
        if expected:
            assert_expected_gaps(result, expected)

    def test_missing_context_when_no_index(self):
        result = run_pipeline_on_case(self.CASE)
        assert result.rag_output is not None, "Pipeline should auto-build a default index when chunk_index is None"

    def test_motion_within_allowed(self):
        result = run_pipeline_on_case(self.CASE)
        assert_expected_motion(result, self.CASE.expected.get("motion_in", []))


class TestGoldenRagSupported:
    CASE = _load("startup_rag_supported")

    def test_pipeline_contract(self):
        result = run_pipeline_on_case(self.CASE)
        assert_pipeline_contract(result)

    def test_rag_does_not_alter_motion(self):
        result_no_rag, result_with_rag = run_pipeline_with_rag(self.CASE)
        assert_rag_does_not_alter_motion(result_no_rag, result_with_rag)

    def test_rag_context_in_brief(self):
        _, result_with_rag = run_pipeline_with_rag(self.CASE)
        brief = build_action_brief(result_with_rag)
        assert len(brief.supporting_nvidia_context) > 0, "Expected supporting NVIDIA context in brief"
        assert len(brief.packed_rag_contexts) > 0

    def test_rag_context_not_in_evidence_used(self):
        _, result_with_rag = run_pipeline_with_rag(self.CASE)
        brief = build_action_brief(result_with_rag)
        assert_rag_context_not_in_evidence_used(brief)


class TestGoldenValidateManually:
    CASE = _load("startup_validate_manually")

    def test_expected_motion(self):
        result = run_pipeline_on_case(self.CASE)
        assert_expected_motion(result, self.CASE.expected.get("motion_in", []))
        assert result.recommended_motion != "immediate_outreach"

    def test_no_approach_now(self):
        result = run_pipeline_on_case(self.CASE)
        assert_no_strong_rec_without_evidence(result)

    def test_max_score(self):
        result = run_pipeline_on_case(self.CASE)
        max_score = self.CASE.expected.get("max_score", 100)
        assert result.final_priority_score <= max_score

    def test_pipeline_contract(self):
        result = run_pipeline_on_case(self.CASE)
        assert_pipeline_contract(result)

    def test_action_brief_sections(self):
        result = run_pipeline_on_case(self.CASE)
        brief = build_action_brief(result)
        assert_action_brief_sections(brief, self.CASE.expected.get("brief_min_sections", 3))


class TestGoldenMonitorOrDiscard:
    CASE = _load("startup_monitor_or_discard")

    def test_expected_motion(self):
        result = run_pipeline_on_case(self.CASE)
        assert_expected_motion(result, self.CASE.expected.get("motion_in", []))

    def test_no_approach_now(self):
        result = run_pipeline_on_case(self.CASE)
        assert_no_strong_rec_without_evidence(result)

    def test_max_score(self):
        result = run_pipeline_on_case(self.CASE)
        assert result.final_priority_score <= self.CASE.expected.get("max_score", 100)

    def test_pipeline_contract(self):
        result = run_pipeline_on_case(self.CASE)
        assert_pipeline_contract(result)


# ---------------------------------------------------------------------------
# Cross-cutting checks
# ---------------------------------------------------------------------------


def test_all_golden_cases_have_expected_outputs():
    """Every golden case file has a corresponding entry in expected_outputs.json."""
    import json

    expected_path = GOLDEN_DIR / "expected_outputs.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    case_ids_in_expected = set(expected.get("cases", {}).keys())

    golden_files = list(GOLDEN_DIR.glob("startup_*.json"))
    case_ids_from_files = set()
    for f in golden_files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        case_ids_from_files.add(raw["case_id"])

    assert case_ids_from_files == case_ids_in_expected, (
        f"Mismatch: golden files have {case_ids_from_files}, " f"expected_outputs has {case_ids_in_expected}"
    )


def test_golden_evals_run_offline():
    """CI should be able to run all golden evals without external services."""
    case = _load("startup_high_fit")
    result = run_pipeline_on_case(case, chunk_index=build_default_index())
    assert result is not None
    assert_pipeline_contract(result)


def test_offline_rag_with_local_embeddings():
    """RAG golden cases work with MockEmbeddingProvider (all-MiniLM-L6-v2)."""
    case = _load("startup_rag_supported")
    _, result = run_pipeline_with_rag(case)
    assert result.rag_output is not None
    brief = build_action_brief(result)
    assert len(brief.supporting_nvidia_context) > 0
