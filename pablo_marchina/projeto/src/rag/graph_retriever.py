"""Graph retrieval helpers for evidence graph benchmark candidates."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.rag.evidence_graph import EvidenceGraphResult


class GraphRetrievalResult(BaseModel):
    paths: list[list[str]] = Field(default_factory=list)
    lineage_coverage: float = Field(ge=0.0, le=1.0)
    source_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


def retrieve_graph_lineage(graph: EvidenceGraphResult, *, top_k: int = 5) -> GraphRetrievalResult:
    paths = graph.lineage_paths[: max(0, top_k)]
    source_count = int(graph.metrics.get("source_count", 0))
    coverage = min(1.0, len(paths) / source_count) if source_count else 0.0
    return GraphRetrievalResult(
        paths=paths,
        lineage_coverage=round(coverage, 4),
        source_count=source_count,
        warnings=graph.warnings,
    )


__all__ = ["GraphRetrievalResult", "retrieve_graph_lineage"]
