from dataclasses import dataclass

from app.rag.catalog import NVIDIA_TECHNOLOGY_CATALOG, NvidiaTechnologyCatalogItem


@dataclass(frozen=True)
class KnowledgeSearchResult:
    name: str
    category: str
    description: str
    source_url: str
    score: float
    matched_keywords: tuple[str, ...]


def search_technology_catalog(query: str, limit: int = 5) -> list[KnowledgeSearchResult]:
    normalized_query = query.lower().strip()
    if not normalized_query:
        return []

    scored_results = [
        _score_catalog_item(normalized_query, catalog_item)
        for catalog_item in NVIDIA_TECHNOLOGY_CATALOG
    ]
    matching_results = [result for result in scored_results if result.score > 0]
    return sorted(matching_results, key=lambda result: result.score, reverse=True)[:limit]


def _score_catalog_item(
    normalized_query: str, catalog_item: NvidiaTechnologyCatalogItem
) -> KnowledgeSearchResult:
    searchable_text = " ".join(
        [
            catalog_item.name,
            catalog_item.category,
            catalog_item.description,
            " ".join(catalog_item.keywords),
        ]
    ).lower()
    query_terms = {term for term in normalized_query.replace("-", " ").split(" ") if term}
    matched_keywords = tuple(
        keyword for keyword in catalog_item.keywords if keyword.lower() in normalized_query
    )

    term_matches = sum(1 for term in query_terms if term in searchable_text)
    keyword_bonus = len(matched_keywords) * 2
    name_bonus = 3 if catalog_item.name.lower() in normalized_query else 0
    score = float(term_matches + keyword_bonus + name_bonus)

    return KnowledgeSearchResult(
        name=catalog_item.name,
        category=catalog_item.category,
        description=catalog_item.description,
        source_url=catalog_item.source_url,
        score=score,
        matched_keywords=matched_keywords,
    )
