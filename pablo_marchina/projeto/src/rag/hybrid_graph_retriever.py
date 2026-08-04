"""Hybrid vector/lexical plus evidence-graph retrieval facade."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.rag.evidence_graph import EvidenceGraphConfig
from src.rag.evidence_graph_builder import build_startup_evidence_graph
from src.rag.graph_retriever import GraphRetrievalResult, retrieve_graph_lineage
from src.rag.schemas import RetrievedContext


class HybridGraphRetrievalResult(BaseModel):
    contexts: list[RetrievedContext] = Field(default_factory=list)
    graph: GraphRetrievalResult
    degraded: bool = False
    fallback_reason: str = ""


def retrieve_with_evidence_graph(
    *,
    contexts: list[RetrievedContext],
    gap_type: str,
    nvidia_technology: str,
    alternatives: list[str] | None = None,
    top_k_paths: int = 5,
    config: EvidenceGraphConfig | None = None,
) -> HybridGraphRetrievalResult:
    graph = build_startup_evidence_graph(
        contexts=contexts,
        gap_type=gap_type,
        nvidia_technology=nvidia_technology,
        alternatives=alternatives,
        config=config,
    )
    graph_result = retrieve_graph_lineage(graph, top_k=top_k_paths)
    degraded = not graph_result.paths
    return HybridGraphRetrievalResult(
        contexts=contexts,
        graph=graph_result,
        degraded=degraded,
        fallback_reason="GRAPH_INDEX_UNAVAILABLE" if degraded else "",
    )


__all__ = ["HybridGraphRetrievalResult", "retrieve_with_evidence_graph"]
