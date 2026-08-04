"""Similar startup retrieval using knowledge graph traversal.

Finds startups with similar gap profiles and technology recommendations
by walking the knowledge graph.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from src.rag.schemas import RetrievedContext


def find_similar_startups(
    kg: Any,
    gaps: list[str],
    technologies: list[str],
    top_k: int = 3,
) -> list[dict]:
    score_by_chunk: Counter[str] = Counter()
    chunk_metadata: dict[str, dict] = {}

    for e in kg.edges:
        if e.relation == "supports_gap":
            gap_name = e.target.replace("gap:", "")
            if gap_name in gaps:
                chunk_id = e.source.replace("chunk:", "")
                score_by_chunk[chunk_id] += 1
                chunk_metadata.setdefault(chunk_id, {})

        if e.relation == "supports_technology":
            tech_name = e.target.replace("tech:", "")
            if tech_name in technologies:
                chunk_id = e.source.replace("chunk:", "")
                score_by_chunk[chunk_id] += 2
                chunk_metadata.setdefault(chunk_id, {})

    for e in kg.edges:
        if e.relation == "maps_to":
            gap_name = e.source.replace("gap:", "")
            tech_name = e.target.replace("tech:", "")
            if gap_name in gaps and tech_name in technologies:
                chunk_ids = e.metadata.get("chunk_ids", [])
                for cid in chunk_ids:
                    score_by_chunk[cid] += 3
                    chunk_metadata.setdefault(cid, {})

    for chunk_id in score_by_chunk:
        node = kg.nodes.get(f"chunk:{chunk_id}")
        if node:
            chunk_metadata[chunk_id] = {
                "chunk_id": chunk_id,
                "title": node.label,
                "url": node.metadata.get("url", ""),
                "product": node.metadata.get("product", ""),
                "content_preview": node.metadata.get("content_preview", "")[:300],
                "similarity_score": (
                    round(score_by_chunk[chunk_id] / max(score_by_chunk.most_common(1)[0][1], 1), 3)
                    if score_by_chunk
                    else 0.0
                ),
            }

    ranked = sorted(chunk_metadata.values(), key=lambda x: -x["similarity_score"])
    return ranked[:top_k]


def retrieve_contexts_by_similarity(
    kg: Any,
    gaps: list[str],
    technologies: list[str],
    top_k: int = 3,
) -> list[RetrievedContext]:
    similar_chunks = find_similar_startups(kg, gaps, technologies, top_k=top_k)
    contexts: list[RetrievedContext] = []
    for chunk_data in similar_chunks:
        node = kg.nodes.get(f"chunk:{chunk_data['chunk_id']}")
        if node:
            ctx = RetrievedContext(
                chunk_id=chunk_data["chunk_id"],
                source_id=node.metadata.get("source_id", ""),
                title=chunk_data["title"],
                content=chunk_data.get("content_preview", ""),
                product=chunk_data.get("product", ""),
                gap_types=[],
                url=chunk_data.get("url", ""),
                relevance_score=chunk_data["similarity_score"],
            )
            contexts.append(ctx)
    return contexts


class SimilarStartupRetrieval:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        kg = kwargs.get("kg")
        gaps = kwargs.get("gaps")
        technologies = kwargs.get("technologies")
        if kg is None or not isinstance(gaps, list) or not isinstance(technologies, list):
            return contexts
        gap_values = [str(item) for item in gaps]
        technology_values = [str(item) for item in technologies]
        if not gap_values or not technology_values:
            return contexts
        return retrieve_contexts_by_similarity(
            kg=kg,
            gaps=gap_values,
            technologies=technology_values,
            top_k=kwargs.get("top_k", 3),
        )
