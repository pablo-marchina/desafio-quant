"""Deterministic query planner for Hybrid RAG.

Transforms startup profile / gaps / claims into structured retrieval
queries. No LLM by default. Pure Python string/keyword logic.
"""

from __future__ import annotations

from src.rag.schemas import QueryPlan

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "because",
        "but",
        "and",
        "or",
        "if",
        "while",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "you",
        "your",
        "we",
        "our",
        "they",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "about",
        "up",
    }
)

_DOC_CATEGORY_MAP: dict[str, list[str]] = {
    "high_inference_cost": ["nim", "tensorrt_llm", "triton"],
    "high_latency": ["nim", "tensorrt_llm", "triton"],
    "external_api_dependency": ["nim"],
    "agent_governance_gap": ["nemo_guardrails"],
    "slow_data_pipeline": ["rapids"],
    "heavy_tabular_processing": ["rapids"],
    "voice_need": ["riva"],
    "simulation_need": ["omniverse"],
    "robotics_need": ["isaac"],
    "healthcare_compliance_need": ["clara_monai"],
    "ai_cybersecurity_need": ["morpheus"],
}


def build_query_plan(
    sector: str = "",
    product_summary: str = "",
    detected_gaps: list[str] | None = None,
    claim_types: list[str] | None = None,
    desired_technologies: list[str] | None = None,
) -> QueryPlan:
    """Build a deterministic query plan from startup context.

    Parameters
    ----------
    sector:
        Startup sector (e.g. \"healthcare\", \"fintech\").
    product_summary:
        Free-text product description.
    detected_gaps:
        List of detected gap type strings.
    claim_types:
        List of claim type strings.
    desired_technologies:
        List of desired NVIDIA technology area names.

    Returns
    -------
    QueryPlan
        Structured plan for retrieval.
    """
    gaps = detected_gaps or []
    techs = desired_technologies or []
    claims = claim_types or []

    # --- primary_query ---
    parts: list[str] = []
    if techs:
        parts.append(" ".join(sorted(techs)))
    if gaps:
        parts.append(" ".join(sorted(g.replace("_", " ") for g in gaps)))
    if not parts and sector:
        parts.append(sector)
    primary_query = " | ".join(parts) if parts else ""

    # --- keyword_query (tokens from product_summary) ---
    tokens = _tokenize(product_summary)
    keyword_query = " ".join(tokens[:8]) if tokens else (sector if sector else "")

    # --- technology_filters ---
    technology_filters = list(dict.fromkeys(techs))

    # --- target_doc_categories ---
    target: list[str] = []
    for gap in gaps:
        target.extend(_DOC_CATEGORY_MAP.get(gap, []))
    for tech in techs:
        t = tech.lower().replace(" ", "_").replace("-", "_")
        if t not in target:
            target.append(t)
    target_doc_categories = list(dict.fromkeys(target))

    # --- must_have_terms ---
    must_have: list[str] = []
    if techs:
        must_have.extend(t.lower() for t in techs)
    if gaps:
        must_have.extend(g.replace("_", " ") for g in gaps)
    if claims:
        must_have.extend(c.replace("_", " ") for c in claims)

    # --- optional_terms ---
    optional_terms = tokens[8:16] if len(tokens) > 8 else []

    # --- metadata_filters ---
    metadata_filters: dict[str, str] = {}
    if target_doc_categories:
        metadata_filters["doc_category"] = ",".join(target_doc_categories)

    return QueryPlan(
        primary_query=primary_query,
        keyword_query=keyword_query,
        technology_filters=technology_filters,
        target_doc_categories=target_doc_categories,
        must_have_terms=list(dict.fromkeys(must_have)),
        optional_terms=list(dict.fromkeys(optional_terms)),
        metadata_filters=metadata_filters,
    )


def _tokenize(text: str) -> list[str]:
    """Split text into lowercased tokens, removing stopwords and short words."""
    if not text:
        return []
    raw = text.lower().split()
    return [w for w in raw if w not in _STOPWORDS and len(w) > 2]
