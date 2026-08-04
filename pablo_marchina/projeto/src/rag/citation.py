"""Citation package for Hybrid RAG evidence.

Builds structured citation objects compatible with Claim Ledger,
Dossier, and Product Quality.
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RagEvidenceChunk, RagEvidenceChunkList


class CitationPackage:
    """Aggregated citation data from a retrieval result.

    Parameters
    ----------
    result:
        RagEvidenceChunkList from HybridRagRetriever.
    """

    def __init__(self, result: RagEvidenceChunkList) -> None:
        self._result = result

    @property
    def citations_json(self) -> list[dict[str, Any]]:
        """Structured citations list for API/UI consumption."""
        return [self._chunk_to_citation(c) for c in self._result.chunks]

    @property
    def evidence_refs_json(self) -> list[dict[str, Any]]:
        """Evidence refs compatible with Claim Ledger evidence_refs_json.

        Each entry has chunk_id, source_url, source_title, and claim.
        """
        refs: list[dict[str, Any]] = []
        for c in self._result.chunks:
            refs.append(
                {
                    "chunk_id": c.chunk_id,
                    "source_url": c.source_url or "",
                    "source_title": c.source_title,
                    "section": c.section,
                    "claim": c.text[:200],
                    "retrieval_mode": c.retrieval_mode,
                    "corpus_version": c.corpus_version,
                }
            )
        return refs

    @property
    def source_coverage_summary(self) -> dict[str, Any]:
        """Summary of source coverage across all chunks."""
        chunks = self._result.chunks
        total = len(chunks)
        if total == 0:
            return {
                "total_chunks": 0,
                "unique_sources": 0,
                "with_url": 0,
                "source_coverage": 0.0,
                "retrieval_mode": self._result.retrieval_mode,
                "degraded": self._result.degraded,
            }

        unique_sources = len({c.chunk_id for c in chunks})
        with_url = sum(1 for c in chunks if c.source_url)

        return {
            "total_chunks": total,
            "unique_sources": unique_sources,
            "with_url": with_url,
            "source_coverage": round(with_url / total, 4) if total > 0 else 0.0,
            "retrieval_mode": self._result.retrieval_mode,
            "degraded": self._result.degraded,
            "fallback_reason": self._result.fallback_reason,
        }

    @staticmethod
    def _chunk_to_citation(chunk: RagEvidenceChunk) -> dict[str, Any]:
        """Convert a single RagEvidenceChunk to a citation dict."""
        return {
            "chunk_id": chunk.chunk_id,
            "source_title": chunk.source_title,
            "source_url": chunk.source_url,
            "section": chunk.section,
            "excerpt": chunk.text[:300],
            "score_dense": chunk.score_dense,
            "score_sparse": chunk.score_sparse,
            "score_fused": chunk.score_fused,
            "score_rerank": chunk.score_rerank,
            "retrieval_mode": chunk.retrieval_mode,
            "corpus_version": chunk.corpus_version,
        }


def build_rag_citation_package(result: RagEvidenceChunkList) -> CitationPackage:
    """Convenience factory for CitationPackage."""
    return CitationPackage(result)
