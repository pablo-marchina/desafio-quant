"""Stable builder facade for GraphRAG evidence graph benchmarks."""

from __future__ import annotations

from src.rag.evidence_graph import EvidenceGraphConfig, EvidenceGraphResult, build_evidence_graph
from src.rag.schemas import RetrievedContext


def build_startup_evidence_graph(
    *,
    contexts: list[RetrievedContext],
    gap_type: str,
    nvidia_technology: str,
    alternatives: list[str] | None = None,
    config: EvidenceGraphConfig | None = None,
) -> EvidenceGraphResult:
    return build_evidence_graph(
        contexts=contexts,
        gap_type=gap_type,
        technology=nvidia_technology,
        alternatives=alternatives,
        config=config,
    )


__all__ = ["EvidenceGraphConfig", "EvidenceGraphResult", "build_startup_evidence_graph"]
