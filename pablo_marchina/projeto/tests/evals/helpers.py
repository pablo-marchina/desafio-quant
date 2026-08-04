"""Helper functions for end-to-end golden pipeline evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import HttpUrl

from src.briefing.schemas import StartupActionBrief
from src.extraction.schemas import (
    ConfidenceLevel,
    Evidence,
    SourceType,
    StartupProfile,
)
from src.pipeline.run_pipeline import PipelineResult, run_full_pipeline
from src.rag.embeddings import MockEmbeddingProvider
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.schemas import PackingConfig, RerankingConfig
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


@dataclass
class GoldenCase:
    case_id: str
    description: str
    profile_data: dict[str, Any]
    evidence_data: list[dict[str, str]]
    expected: dict[str, Any] = field(default_factory=dict)

    def build_profile(self) -> StartupProfile:
        p = self.profile_data
        return StartupProfile(
            startup_name=self.case_id,
            website=HttpUrl("https://example.com"),
            sector=p.get("sector", "Technology"),
            description=p.get("description", ""),
            product_summary=p.get("product_summary", ""),
            ai_signals=p.get("ai_signals", []),
            tech_stack_signals=p.get("tech_stack", []),
            customers=p.get("customers", []),
            funding_signals=p.get("funding", []),
            sources=[],
            confidence_score=0.6,
        )

    def build_evidence(self) -> list[Evidence]:
        return [
            Evidence(
                claim=e["claim"],
                source_url=HttpUrl("https://example.com"),
                source_type=SourceType.OFFICIAL_SITE,
                quote_or_evidence=e["claim"],
                confidence=ConfidenceLevel(e["confidence"]),
                collected_at=datetime.now(UTC),
            )
            for e in self.evidence_data
        ]


def load_golden_case(path: str | Path) -> GoldenCase:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return GoldenCase(
        case_id=raw["case_id"],
        description=raw.get("description", ""),
        profile_data=raw["profile"],
        evidence_data=raw.get("evidence", []),
        expected=raw.get("expected", {}),
    )


def load_expected_outputs(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw.get("cases", {})


def run_pipeline_on_case(
    case: GoldenCase,
    chunk_index: ChunkIndex | None = None,
) -> PipelineResult:
    profile = case.build_profile()
    evidence = case.build_evidence()
    return run_full_pipeline(
        startup_name=case.case_id,
        profile=profile,
        evidence_list=evidence,
        chunk_index=chunk_index,
    )


def run_pipeline_with_rag(case: GoldenCase) -> tuple[PipelineResult, PipelineResult]:
    chunk_index = build_default_index()
    embedding = MockEmbeddingProvider()
    vector_store = InMemoryVectorStore()
    vector_store.add_entries(
        [
            VectorEntry(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                title=chunk.title,
                content=chunk.content,
                product=chunk.product,
                gap_types=list(chunk.gap_types),
                url=chunk.url,
                embedding=embedding.embed(chunk.content),
                version=chunk.version,
                document_type=chunk.document_type,
                content_hash=chunk.content_hash,
                previous_content_hash=chunk.previous_content_hash,
                collected_at=chunk.collected_at,
                last_checked_at=chunk.last_checked_at,
                valid_from=chunk.valid_from,
                valid_until=chunk.valid_until,
                freshness_policy=chunk.freshness_policy,
                stale_after_days=chunk.stale_after_days,
                is_active=chunk.is_active,
                deprecated_at=chunk.deprecated_at,
                superseded_by=chunk.superseded_by,
                deprecation_reason=chunk.deprecation_reason,
                nvidia_technology=chunk.nvidia_technology,
                corpus_version=chunk.corpus_version,
                chunk_index=chunk.chunk_index,
                char_count=chunk.char_count,
            )
            for chunk in chunk_index.chunks
        ]
    )
    rerank_config = RerankingConfig()
    pack_config = PackingConfig()

    result_no_rag = run_pipeline_on_case(case)

    result_with_rag = run_full_pipeline(
        startup_name=case.case_id,
        profile=case.build_profile(),
        evidence_list=case.build_evidence(),
        chunk_index=chunk_index,
        embedding_model=embedding,
        vector_store=vector_store,
        reranking_config=rerank_config,
        packing_config=pack_config,
    )
    return result_no_rag, result_with_rag


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------


def assert_pipeline_contract(result: PipelineResult) -> None:
    assert result.startup_name, "startup_name must be non-empty"
    assert result.startup_profile is not None
    assert result.ai_native_classification is not None
    assert isinstance(result.validated_evidence, list)
    assert result.defensibility_score is not None
    assert result.inception_fit_score is not None
    assert result.production_readiness_score is not None
    assert result.composite_score is not None
    assert isinstance(result.ranked, list) and len(result.ranked) > 0
    assert 0 <= result.final_priority_score <= 100
    assert result.recommended_motion in (
        "immediate_outreach",
        "high_priority_outreach",
        "monitor_and_nurture",
        "lack_evidence_more_research",
        "not_recommended",
    )
    assert result.gap_diagnosis is not None
    assert result.recommendation is not None
    assert isinstance(result.evidence_used, list)
    assert isinstance(result.missing_evidence, list)
    assert isinstance(result.reasoning, str) and len(result.reasoning) > 0


def assert_expected_motion(result: PipelineResult, allowed_motions: list[str]) -> None:
    assert result.recommended_motion in allowed_motions, (
        f"Expected motion in {allowed_motions}, " f"got {result.recommended_motion}"
    )


def assert_expected_gaps(result: PipelineResult, expected_gaps: list[str]) -> None:
    diag = result.gap_diagnosis
    assert diag is not None
    detected = {g.gap.value for g in diag.diagnosed_gaps if g.detected}
    for gap in expected_gaps:
        assert gap in detected, f"Expected gap {gap} not detected. " f"Detected gaps: {detected}"


def assert_no_tech_without_gap(result: PipelineResult) -> None:
    rec = result.recommendation
    assert rec is not None
    for pg in rec.recommendations:
        if not pg.detected:
            assert len(pg.recommended_nvidia_technologies) == 0, (
                f"Undetected gap {pg.diagnosed_gap} has technologies: " f"{pg.recommended_nvidia_technologies}"
            )


def assert_missing_evidence_propagates(result: PipelineResult) -> None:
    diag = result.gap_diagnosis
    rec = result.recommendation
    assert diag is not None
    assert rec is not None
    if diag.missing_evidence:
        for item in diag.missing_evidence:
            assert item in result.missing_evidence, (
                f"missing_evidence '{item}' from diagnosis " f"not propagated to PipelineResult"
            )
    if rec.missing_evidence:
        for item in rec.missing_evidence:
            assert item in result.missing_evidence, (
                f"missing_evidence '{item}' from recommendation " f"not propagated to PipelineResult"
            )


def assert_confidence_coherent(result: PipelineResult) -> None:
    evidence = result.validated_evidence
    high_count = sum(1 for e in evidence if e.confidence == ConfidenceLevel.HIGH)
    if high_count == 0 and result.ai_native_classification.confidence in (
        ConfidenceLevel.HIGH,
        ConfidenceLevel.MEDIUM,
    ):
        assert result.composite_score.confidence != ConfidenceLevel.HIGH


def assert_action_brief_sections(brief: StartupActionBrief, min_sections: int) -> None:
    assert len(brief.sections) >= min_sections, (
        f"Expected at least {min_sections} sections, " f"got {len(brief.sections)}"
    )
    section_titles = {s.title for s in brief.sections}
    required = {"Executive Summary", "Evidence"}
    missing = required - section_titles
    assert not missing, f"Missing required brief sections: {missing}"


def assert_no_strong_rec_without_evidence(result: PipelineResult) -> None:
    rec = result.recommendation
    assert rec is not None
    for pg in rec.recommendations:
        if pg.action == "approach_now":
            has_high = any(e.confidence == ConfidenceLevel.HIGH for e in result.validated_evidence)
            assert has_high, f"approach_now recommendation for {pg.diagnosed_gap} " f"but no HIGH confidence evidence"


def assert_rag_does_not_alter_motion(result_no_rag: PipelineResult, result_with_rag: PipelineResult) -> None:
    assert result_no_rag.recommended_motion == result_with_rag.recommended_motion, (
        f"RAG altered recommended_motion: "
        f"{result_no_rag.recommended_motion} -> {result_with_rag.recommended_motion}"
    )


def assert_rag_context_not_in_evidence_used(
    brief: StartupActionBrief,
) -> None:
    context_content = set()
    for ctx in brief.supporting_nvidia_context:
        context_content.add(ctx.gap_type)
        context_content.add(ctx.technology)
    for ev in brief.evidence_used:
        assert ev.claim not in context_content, f"RAG context claim appears in evidence_used: {ev.claim}"
