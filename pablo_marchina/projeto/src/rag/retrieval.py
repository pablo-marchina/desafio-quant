"""Governed lexical retrieval over NVIDIA corpus chunks."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import yaml

from src.rag.schemas import RagChunk, RetrievalQuery, RetrievedContext

_DEFAULT_TOP_K = 3
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_KEYWORDS_FILE = _PROJECT_ROOT / "data" / "nvidia_corpus" / "retrieval_keywords.yaml"


class ChunkIndex:
    """In-memory index over corpus chunks for deterministic lexical retrieval."""

    def __init__(self, chunks: list[RagChunk] | None = None) -> None:
        self.chunks: list[RagChunk] = chunks or []
        self.by_gap: dict[str, list[RagChunk]] = {}
        self.by_tech: dict[str, list[RagChunk]] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        self.by_gap.clear()
        self.by_tech.clear()
        for chunk in self.chunks:
            for gap in chunk.gap_types:
                self.by_gap.setdefault(gap, []).append(chunk)
            tech_key = _normalize_technology(chunk.product)
            self.by_tech.setdefault(tech_key, []).append(chunk)

    def _candidates_from_query(self, query: RetrievalQuery) -> list[RagChunk]:
        """Return candidates using conjunctive structured filters.

        A query that specifies both a gap and a technology is an intersection,
        not a union. Keyword recall is governed by the source alias registry,
        so downloaded page chrome cannot make an unrelated source eligible.
        """
        if not query.gap_type and not query.technology and not query.keywords:
            return []

        if query.gap_type:
            candidates = list(self.by_gap.get(query.gap_type, []))
        elif query.technology:
            candidates = list(self.by_tech.get(_normalize_technology(query.technology), []))
        else:
            candidates = list(self.chunks)

        if query.technology:
            candidates = [chunk for chunk in candidates if _technology_matches(chunk, query.technology)]

        if query.keywords:
            candidates = [chunk for chunk in candidates if _keywords_match(chunk, query.keywords)]

        unique: list[RagChunk] = []
        seen: set[str] = set()
        for chunk in candidates:
            if chunk.chunk_id in seen or not _is_retrievable(chunk, query):
                continue
            seen.add(chunk.chunk_id)
            unique.append(chunk)
        return unique

    def retrieve(
        self,
        query: RetrievalQuery,
        top_k: int = _DEFAULT_TOP_K,
    ) -> list[RetrievedContext]:
        candidates = self._candidates_from_query(query)
        if not candidates or top_k <= 0:
            return []

        scored = [_score_chunk(chunk, query) for chunk in candidates]
        top = _source_diverse_top(scored, top_k)
        return [ctx for ctx, _ in top]

    def retrieve_by_gap_type(
        self,
        gap_type: str,
        top_k: int = _DEFAULT_TOP_K,
    ) -> list[RetrievedContext]:
        return self.retrieve(RetrievalQuery(gap_type=gap_type), top_k=top_k)

    def retrieve_by_technology(
        self,
        technology: str,
        top_k: int = _DEFAULT_TOP_K,
    ) -> list[RetrievedContext]:
        return self.retrieve(RetrievalQuery(technology=technology), top_k=top_k)


def _normalize_technology(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _normalize_keyword(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


@lru_cache(maxsize=1)
def _load_retrieval_keywords() -> dict[str, set[str]]:
    if not _KEYWORDS_FILE.is_file():
        return {}
    raw = yaml.safe_load(_KEYWORDS_FILE.read_text(encoding="utf-8")) or {}
    mapping = raw.get("keywords", {})
    if not isinstance(mapping, dict):
        return {}

    normalized: dict[str, set[str]] = {}
    for source_id, values in mapping.items():
        if not isinstance(values, list):
            continue
        aliases = {_normalize_keyword(str(value)) for value in values if str(value).strip()}
        normalized[str(source_id)] = {alias for alias in aliases if alias}
    return normalized


def reset_retrieval_keyword_cache() -> None:
    """Clear the governed keyword registry cache for deterministic tests."""
    _load_retrieval_keywords.cache_clear()


def _technology_matches(chunk: RagChunk, technology: str) -> bool:
    wanted = _normalize_technology(technology)
    if not wanted:
        return True
    product = _normalize_technology(chunk.product)
    nvidia_technology = _normalize_technology(chunk.nvidia_technology or "")
    return wanted in {product, nvidia_technology}


def _source_aliases(chunk: RagChunk) -> set[str]:
    governed = set(_load_retrieval_keywords().get(chunk.source_id, set()))
    governed.add(_normalize_keyword(chunk.product))
    governed.add(_normalize_keyword(chunk.title))
    return {alias for alias in governed if alias}


def _keyword_hits(chunk: RagChunk, keywords: list[str]) -> int:
    aliases = _source_aliases(chunk)
    normalized_queries = [_normalize_keyword(keyword) for keyword in keywords if keyword.strip()]
    return sum(
        1
        for query in normalized_queries
        if query and any(query == alias or query in alias or alias in query for alias in aliases)
    )


def _keywords_match(chunk: RagChunk, keywords: list[str]) -> bool:
    return _keyword_hits(chunk, keywords) > 0


def _source_diverse_top(
    scored: list[tuple[RetrievedContext, float]],
    top_k: int,
) -> list[tuple[RetrievedContext, float]]:
    """Rank by relevance while guaranteeing source coverage before duplicates.

    Golden and production queries frequently request a gap addressed by several
    NVIDIA technologies. Taking the first ``k`` tied chunks allowed one verbose
    document to occupy every slot. We first select the best chunk per source,
    then fill remaining capacity with the next best chunks.
    """
    ranked = sorted(scored, key=lambda item: (-item[1], item[0].source_id, item[0].chunk_id))
    by_source: dict[str, list[tuple[RetrievedContext, float]]] = defaultdict(list)
    for item in ranked:
        by_source[item[0].source_id].append(item)

    source_heads = sorted(
        (items[0] for items in by_source.values()),
        key=lambda item: (-item[1], item[0].source_id, item[0].chunk_id),
    )
    selected = source_heads[:top_k]
    selected_ids = {item[0].chunk_id for item in selected}

    if len(selected) < top_k:
        for item in ranked:
            if item[0].chunk_id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item[0].chunk_id)
            if len(selected) == top_k:
                break

    return selected


def _score_chunk(chunk: RagChunk, query: RetrievalQuery) -> tuple[RetrievedContext, float]:
    """Score a chunk's relevance to a query (0.0 to 1.0)."""
    score = 0.0

    if query.gap_type and query.gap_type in chunk.gap_types:
        score += 0.45

    if query.technology and _technology_matches(chunk, query.technology):
        score += 0.3

    if query.keywords:
        matched = _keyword_hits(chunk, query.keywords)
        if matched > 0:
            score += 0.3 * min(matched / len(query.keywords), 1.0)

    score = min(score, 1.0)
    context = RetrievedContext(
        chunk_id=chunk.chunk_id,
        source_id=chunk.source_id,
        title=chunk.title,
        content=chunk.content,
        product=chunk.product,
        gap_types=list(chunk.gap_types),
        url=chunk.url,
        relevance_score=round(score, 4),
        version=chunk.version,
        collected_at=chunk.collected_at,
        last_checked_at=chunk.last_checked_at,
        valid_from=chunk.valid_from,
        valid_until=chunk.valid_until,
        freshness_policy=chunk.freshness_policy,
        stale_after_days=chunk.stale_after_days,
        is_active=chunk.is_active,
        deprecated_at=chunk.deprecated_at,
        superseded_by=chunk.superseded_by,
    )
    return context, score


def _select_source_diverse(
    scored: list[tuple[RetrievedContext, float]],
    query: RetrievalQuery,
    top_k: int,
) -> list[tuple[RetrievedContext, float]]:
    """Round-robin high-quality results across sources for broad queries.

    Specific technology queries intentionally stay concentrated on the selected
    product. Gap-only and keyword-only queries benefit from source diversity,
    because a long document can otherwise consume every result slot.
    """
    if query.technology or len(scored) <= 1:
        return scored[:top_k]

    buckets: dict[str, list[tuple[RetrievedContext, float]]] = {}
    source_order: list[str] = []
    for item in scored:
        source_id = item[0].source_id
        if source_id not in buckets:
            buckets[source_id] = []
            source_order.append(source_id)
        buckets[source_id].append(item)

    selected: list[tuple[RetrievedContext, float]] = []
    cursor = 0
    while len(selected) < top_k:
        added = False
        for source_id in source_order:
            bucket = buckets[source_id]
            if cursor < len(bucket):
                selected.append(bucket[cursor])
                added = True
                if len(selected) == top_k:
                    break
        if not added:
            break
        cursor += 1
    return selected


def _deduplicate(chunks: list[RagChunk]) -> list[RagChunk]:
    seen: set[str] = set()
    result: list[RagChunk] = []
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        result.append(chunk)
    return result


def _is_retrievable(chunk: RagChunk, query: RetrievalQuery) -> bool:
    if not query.include_deprecated:
        if chunk.is_active is not True:
            return False
        if chunk.deprecated_at or chunk.superseded_by:
            return False
    if not query.include_expired and _is_expired(chunk.valid_until):
        return False
    return True


def _is_expired(valid_until: str | None) -> bool:
    if not valid_until:
        return False
    try:
        parsed = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC) < datetime.now(UTC)


def build_default_index() -> ChunkIndex:
    """Build index from the default corpus directory."""
    from src.rag.ingestion import load_and_chunk_corpus

    chunks = load_and_chunk_corpus()
    return ChunkIndex(chunks)
