"""Sparse retrieval v1 — BM25-style keyword scoring over corpus chunks.

Pure Python, no external dependencies.  Uses TF-IDF-like scoring with
IDF pre-computed from the corpus.

Epic 42: Sparse retrieval strategy — BM25 local proxy.
"""

from __future__ import annotations

import math
from collections import Counter

from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext


class SparseRetriever:
    """BM25-style keyword retriever over a ChunkIndex.

    Parameters
    ----------
    index:
        ChunkIndex with corpus chunks.
    k1:
        BM25 saturation parameter (default 1.5).
    b:
        BM25 length normalization parameter (default 0.75).
    """

    def __init__(
        self,
        index: ChunkIndex,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self._index = index
        self._k1 = k1
        self._b = b
        self._avg_doc_len: float = 0.0
        self._idf: dict[str, float] = {}
        self._doc_lens: list[int] = []
        self._doc_tokens: list[Counter] = []
        self._build_index()

    def _build_index(self) -> None:
        """Pre-compute IDF and document lengths from corpus chunks."""
        chunks = self._index.chunks
        if not chunks:
            return

        doc_count = len(chunks)
        df: Counter[str] = Counter()
        self._doc_tokens = []
        self._doc_lens = []

        for c in chunks:
            tokens = _tokenize_chunk(c.content)
            unique = set(tokens)
            for t in unique:
                df[t] += 1
            self._doc_tokens.append(Counter(tokens))
            self._doc_lens.append(len(tokens))

        self._avg_doc_len = sum(self._doc_lens) / max(doc_count, 1)

        for term, doc_freq in df.items():
            self._idf[term] = math.log(1.0 + (doc_count - doc_freq + 0.5) / (doc_freq + 0.5))

    @property
    def is_ready(self) -> bool:
        """True if the index has been built."""
        return bool(self._idf)

    def retrieve(
        self,
        query: RetrievalQuery,
        top_k: int = 3,
    ) -> list[RetrievedContext]:
        """Score all chunks by BM25 against the query and return top_k."""
        if not self._idf or not self._index.chunks:
            return []

        query_terms = _query_terms(query)
        if not query_terms:
            if query.keywords:
                query_terms = [kw.lower() for kw in query.keywords]
            else:
                return []

        scored: list[tuple[int, float]] = []
        for doc_idx, chunk in enumerate(self._index.chunks):
            if not _is_retrievable_via_sparse(chunk, query):
                continue
            score = self._bm25_score(doc_idx, query_terms)
            if score > 0.0:
                scored.append((doc_idx, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        results: list[RetrievedContext] = []
        for doc_idx, score in top:
            chunk = self._index.chunks[doc_idx]
            ctx = RetrievedContext(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                title=chunk.title,
                content=chunk.content,
                product=chunk.product,
                gap_types=list(chunk.gap_types),
                url=chunk.url,
                relevance_score=round(min(score, 1.0), 2),
                version=chunk.version,
                valid_from=chunk.valid_from,
                valid_until=chunk.valid_until,
                freshness_policy=chunk.freshness_policy,
                stale_after_days=chunk.stale_after_days,
                is_active=chunk.is_active,
                deprecated_at=chunk.deprecated_at,
                superseded_by=chunk.superseded_by,
            )
            results.append(ctx)

        return results

    def _bm25_score(self, doc_idx: int, query_terms: list[str]) -> float:
        """Compute BM25 score for a single document."""
        doc_len = self._doc_lens[doc_idx]
        term_freqs = self._doc_tokens[doc_idx]
        score = 0.0
        for term in query_terms:
            tf = term_freqs.get(term, 0)
            if tf == 0:
                continue
            idf = self._idf.get(term, 0.0)
            if idf <= 0:
                continue
            numerator = tf * (self._k1 + 1)
            denominator = tf + self._k1 * (1 - self._b + self._b * doc_len / self._avg_doc_len)
            score += idf * numerator / denominator
        return score


def _tokenize_chunk(text: str) -> list[str]:
    """Lowercase, split on whitespace/punctuation, keep 2+ char tokens."""
    import re

    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return [t for t in tokens if len(t) > 1]


def _query_terms(query: RetrievalQuery) -> list[str]:
    """Extract search terms from a RetrievalQuery."""
    terms: list[str] = []
    if query.gap_type:
        terms.extend(query.gap_type.replace("_", " ").split())
    if query.technology:
        terms.extend(query.technology.replace("_", " ").split())
    if query.keywords:
        terms.extend(kw.lower() for kw in query.keywords)
    return list(dict.fromkeys(terms))


def _is_retrievable_via_sparse(chunk: object, query: RetrievalQuery) -> bool:
    """Check lifecycle filters."""
    if not hasattr(chunk, "is_active") or not hasattr(chunk, "valid_until"):
        return True
    if not query.include_deprecated:
        if getattr(chunk, "is_active", True) is not True:
            return False
        if getattr(chunk, "deprecated_at", None) or getattr(chunk, "superseded_by", None):
            return False
    if not query.include_expired:
        from src.rag.retrieval import _is_expired

        if _is_expired(getattr(chunk, "valid_until", None)):
            return False
    return True
