"""Deterministic HyDE — generate hypothetical ideal documents from query metadata.

No LLM calls. Uses gap_type, technology, and keywords to construct a
template-based hypothetical document that would be the ideal retrieval result.
The hypothetical document is then embedded instead of the raw query,
improving semantic retrieval recall by aligning query and document in
embedding space.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.embeddings import EmbeddingProvider
from src.rag.schemas import RetrievalQuery, RetrievedContext
from src.rag.vector_store import VectorStore

_HYDE_TEMPLATES: dict[str, str] = {
    "high_inference_cost": (
        "This document describes how to optimize inference costs for AI models "
        "using NVIDIA Triton Inference Server, TensorRT-LLM, and GPU optimization "
        "techniques. Key topics include: reducing latency, increasing throughput, "
        "model quantization, batch processing, and deploying self-hosted inference endpoints "
        "with NVIDIA NIM microservices."
    ),
    "high_latency": (
        "This document covers NVIDIA solutions for reducing AI inference latency "
        "including Triton Inference Server's dynamic batching, TensorRT-LLM optimization, "
        "FP16/INT8 quantization, and real-time model serving with NVIDIA NIM. "
        "Focus areas: real-time inference, latency reduction, GPU acceleration, "
        "and efficient model deployment."
    ),
    "external_api_dependency": (
        "This document explains how to deploy NVIDIA AI models in self-hosted "
        "production environments using NVIDIA NIM (NVIDIA Inference Microservices). "
        "Topics include: on-premises deployment, containerized model serving, "
        "Triton Inference Server setup, and reducing external API dependencies "
        "by running NVIDIA models locally."
    ),
    "agent_governance_gap": (
        "This document describes NVIDIA NeMo Guardrails for AI agent safety and "
        "governance. Covers: policy-based guardrails, alignment safeguarding, "
        "content safety filters, output validation, and monitoring for AI agent "
        "behavior. Ensures AI agents operate within defined safety boundaries."
    ),
    "slow_data_pipeline": (
        "This document explains how to accelerate data processing pipelines using "
        "NVIDIA RAPIDS (cuDF, cuML, cuGraph) for GPU-accelerated dataframes, "
        "ML, and graph analytics. Topics include: GPU data processing, ETL "
        "acceleration, large-scale data analytics, and integrating RAPIDS with "
        "existing data workflows."
    ),
    "voice_need": (
        "This document covers NVIDIA RIVA for speech AI — ASR (automatic speech "
        "recognition), TTS (text-to-speech), and neural voice synthesis. "
        "Topics: real-time speech processing, custom voice models, multilingual "
        "support, and deploying speech AI at scale with GPU acceleration."
    ),
}

_DEFAULT_HYDE_TEMPLATE = (
    "This document describes NVIDIA GPU-accelerated AI solutions for "
    "{gap_description}. It covers relevant NVIDIA technologies including "
    "{tech_list}, deployment patterns, best practices, and integration guides "
    "for production AI systems."
)


class HyDEConfig(BaseModel):
    enabled: bool = True
    hybrid_alpha: float = 0.7


def generate_hypothetical_document(query: RetrievalQuery, config: HyDEConfig | None = None) -> str:
    """Generate a hypothetical ideal document from query metadata.

    Uses gap_type-specific templates to construct a document that would be
    the ideal retrieval result. Falls back to a generic template.

    Parameters
    ----------
    query:
        The retrieval query with gap_type, technology, and keywords.
    config:
        HyDE configuration. If None, uses defaults.

    Returns
    -------
    str
        Hypothetical document text to embed instead of the raw query.
    """
    cfg = config or HyDEConfig()
    if not cfg.enabled:
        return _build_query_text(query)

    gap_type = query.gap_type or ""
    technology = query.technology or ""
    keywords = query.keywords or []

    template = _HYDE_TEMPLATES.get(gap_type, _DEFAULT_HYDE_TEMPLATE)

    if gap_type in _HYDE_TEMPLATES:
        result = template
        if technology:
            result += f" Specific NVIDIA technology: {technology}."
        if keywords:
            result += f" Related topics: {', '.join(keywords)}."
        return result

    gap_description = gap_type.replace("_", " ")
    tech_list = ", ".join({technology, *keywords}) if technology or keywords else "NVIDIA AI"
    return template.format(gap_description=gap_description, tech_list=tech_list)


def hyde_retrieve(
    query: RetrievalQuery,
    embedding_model: EmbeddingProvider,
    vector_store: VectorStore,
    top_k: int = 3,
    config: HyDEConfig | None = None,
    *,
    product: str | None = None,
    gap_type: str | None = None,
    source_id: str | None = None,
    include_deprecated: bool = False,
    include_expired: bool = False,
) -> list[RetrievedContext]:
    """Retrieve using HyDE: generate hypothetical doc → embed → search.

    Uses a weighted combination of:
    - HyDE embedding (alpha * hyde_vec)
    - Raw query embedding ((1-alpha) * query_vec)

    Parameters
    ----------
    query:
        The retrieval query.
    embedding_model:
        Embedding provider.
    vector_store:
        Vector store.
    top_k:
        Maximum contexts to return.
    config:
        HyDE config with alpha weight.
    product, gap_type, source_id:
        Optional metadata filters.

    Returns
    -------
    list[RetrievedContext]
        Retrieved contexts sorted by relevance.
    """
    from src.rag.semantic_retrieval import semantic_retrieve

    cfg = config or HyDEConfig()
    if not cfg.enabled:
        return semantic_retrieve(query, embedding_model, vector_store, top_k=top_k)

    hyde_doc = generate_hypothetical_document(query, cfg)
    hyde_vector = embedding_model.embed(hyde_doc)
    query_text = _build_query_text(query)
    query_vector = embedding_model.embed(query_text)

    alpha = cfg.hybrid_alpha
    combined = [alpha * hv + (1.0 - alpha) * qv for hv, qv in zip(hyde_vector, query_vector, strict=False)]

    results = vector_store.search(
        combined,
        top_k=top_k,
        product=product,
        gap_type=gap_type or query.gap_type,
        source_id=source_id,
        include_deprecated=include_deprecated,
        include_expired=include_expired,
    )

    from src.rag.semantic_retrieval import _compute_relevance_from_similarity

    contexts: list[RetrievedContext] = []
    for entry in results:
        score = _compute_relevance_from_similarity(entry, query)
        contexts.append(
            RetrievedContext(
                chunk_id=entry.chunk_id,
                source_id=entry.source_id,
                title=entry.title,
                content=entry.content,
                product=entry.product,
                gap_types=list(entry.gap_types),
                url=entry.url,
                relevance_score=score,
                version=entry.version,
                valid_from=entry.valid_from,
                valid_until=entry.valid_until,
                freshness_policy=entry.freshness_policy,
                stale_after_days=entry.stale_after_days,
                is_active=entry.is_active,
                deprecated_at=entry.deprecated_at,
                superseded_by=entry.superseded_by,
            )
        )
    return contexts


def _build_query_text(query: RetrievalQuery) -> str:
    parts: list[str] = []
    if query.gap_type:
        parts.append(query.gap_type.replace("_", " "))
    if query.technology:
        parts.append(query.technology)
    if query.keywords:
        parts.extend(query.keywords)
    return " ".join(parts) if parts else ""


class Hyde:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query")
        embedding_model = kwargs.get("embedding_model")
        vector_store = kwargs.get("vector_store")
        if (
            not isinstance(query, RetrievalQuery)
            or not isinstance(embedding_model, EmbeddingProvider)
            or not isinstance(vector_store, VectorStore)
        ):
            return contexts
        config = kwargs.get("config")
        if config is not None and not isinstance(config, HyDEConfig):
            config = HyDEConfig(**config) if isinstance(config, dict) else None
        return hyde_retrieve(
            query=query,
            embedding_model=embedding_model,
            vector_store=vector_store,
            top_k=kwargs.get("top_k", 3),
            config=config,
            product=kwargs.get("product"),
            gap_type=kwargs.get("gap_type"),
            source_id=kwargs.get("source_id"),
            include_deprecated=kwargs.get("include_deprecated", False),
            include_expired=kwargs.get("include_expired", False),
        )
