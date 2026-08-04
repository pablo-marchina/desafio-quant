"""Evidence refs helpers for Claim Ledger integration.

Converts RagEvidenceChunk data into the evidence_refs format
used by Claim Ledger records.
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RagEvidenceChunk, RagEvidenceChunkList


def evidence_refs_from_chunks(chunks: list[RagEvidenceChunk]) -> list[dict[str, Any]]:
    """Build evidence_refs list from RagEvidenceChunks for Claim Ledger.

    Each ref is compatible with the evidence_refs_json format used
    in ClaimRecord and ScoreRecord models.
    """
    refs: list[dict[str, Any]] = []
    for c in chunks:
        refs.append(
            {
                "chunk_id": c.chunk_id,
                "source_url": c.source_url or "",
                "source_title": c.source_title,
                "section": c.section,
                "claim": c.text[:200],
                "score_fused": c.score_fused,
                "score_rerank": c.score_rerank,
                "retrieval_mode": c.retrieval_mode,
            }
        )
    return refs


def evidence_refs_from_result(result: RagEvidenceChunkList) -> list[dict[str, Any]]:
    """Build evidence_refs from a complete retrieval result."""
    return evidence_refs_from_chunks(result.chunks)


def citation_section_for_dossier(
    result: RagEvidenceChunkList,
    max_chunks: int = 5,
) -> dict[str, Any]:
    """Build an optional citation section for the Activation Dossier.

    Returns dict with citations and coverage metadata, ready to be
    included as an optional field in dossier_json.
    """
    from src.rag.citation import build_rag_citation_package

    pkg = build_rag_citation_package(result)
    citations = pkg.citations_json[:max_chunks]

    return {
        "rag_citations": citations,
        "source_coverage": pkg.source_coverage_summary,
        "total_citations": len(citations),
        "total_raw": result.total_raw,
        "retrieval_mode": result.retrieval_mode,
        "degraded": result.degraded,
    }
