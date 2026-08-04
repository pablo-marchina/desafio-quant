from typing import Any
import re
import unicodedata

from fastapi import HTTPException

from app.rag.schemas import HybridCandidate


RERANKER_MODEL_NAME = (
    "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
)

_reranker_model: Any | None = None

MAX_DOCUMENT_CHARS = 1800

MODEL_WEIGHT = 0.65
METADATA_WEIGHT = 0.35

MIN_RERANK_SCORE = 0.55
FALLBACK_MIN_RERANK_SCORE = 0.45

MIN_CONTENT_ALIGNMENT = 0.25
FALLBACK_MIN_CONTENT_ALIGNMENT = 0.50

MAX_EVIDENCES_PER_TECHNOLOGY = 2


CONCEPT_KEYWORDS = {
    "llm": {
        "llm",
        "llms",
        "language",
        "linguagem",
        "token",
        "tokens",
    },
    "performance": {
        "latencia",
        "latency",
        "throughput",
        "inferencia",
        "inference",
        "batching",
        "otimizacao",
        "optimization",
    },
    "production": {
        "producao",
        "production",
        "deploy",
        "deployment",
        "serving",
        "microservices",
        "microservicos",
    },
    "governance": {
        "guardrails",
        "governanca",
        "governance",
        "seguranca",
        "safety",
        "validacao",
        "validation",
        "jailbreak",
        "pii",
    },
    "retrieval": {
        "rag",
        "retrieval",
        "embedding",
        "embeddings",
        "reranking",
        "documentos",
        "documents",
    },
}


CONCEPT_WEIGHTS = {
    "llm": 1.5,
    "performance": 2.0,
    "production": 1.2,
    "governance": 2.0,
    "retrieval": 2.0,
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize(
        "NFD",
        text.casefold(),
    )

    without_accents = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        without_accents,
    ).strip()


def get_concepts(text: str) -> set[str]:
    words = set(normalize_text(text).split())

    return {
        concept
        for concept, keywords in CONCEPT_KEYWORDS.items()
        if words & keywords
    }


def calculate_concept_alignment(
    query: str,
    text: str,
) -> float:
    query_concepts = get_concepts(query)

    if not query_concepts:
        return 1.0

    text_concepts = get_concepts(text)
    matched_concepts = query_concepts & text_concepts

    matched_weight = sum(
        CONCEPT_WEIGHTS[concept]
        for concept in matched_concepts
    )

    total_weight = sum(
        CONCEPT_WEIGHTS[concept]
        for concept in query_concepts
    )

    if total_weight == 0:
        return 0.0

    return matched_weight / total_weight


def build_candidate_context(candidate: HybridCandidate) -> str:
    document_preview = candidate.text[:MAX_DOCUMENT_CHARS]

    return (
        f"Technology: {candidate.technology_name}\n"
        f"Title: {candidate.title}\n"
        f"Tags: {', '.join(candidate.tags)}\n"
        f"Documentation: {document_preview}"
    )


def calculate_metadata_alignment(
    query: str,
    candidate: HybridCandidate,
) -> float:
    return calculate_concept_alignment(
        query=query,
        text=build_candidate_context(candidate),
    )


def calculate_content_alignment(
    query: str,
    candidate: HybridCandidate,
) -> float:
    return calculate_concept_alignment(
        query=query,
        text=candidate.text,
    )


def get_reranker_model() -> Any:
    global _reranker_model

    if _reranker_model is None:
        try:
            import torch
            from sentence_transformers import CrossEncoder

            _reranker_model = CrossEncoder(
                RERANKER_MODEL_NAME,
                activation_fn=torch.nn.Sigmoid(),
            )
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Não foi possível carregar o modelo de reranking: "
                    f"{error}"
                ),
            )

    return _reranker_model


def limit_evidences_per_technology(
    candidates: list[HybridCandidate],
    top_k: int,
) -> list[HybridCandidate]:
    selected: list[HybridCandidate] = []
    technology_counts: dict[str, int] = {}

    for candidate in candidates:
        if len(selected) >= top_k:
            break

        current_count = technology_counts.get(
            candidate.technology_id,
            0,
        )

        if current_count >= MAX_EVIDENCES_PER_TECHNOLOGY:
            continue

        selected.append(candidate)

        technology_counts[candidate.technology_id] = (
            current_count + 1
        )

    return selected


def rerank_candidates(
    query: str,
    candidates: list[HybridCandidate],
    top_k: int,
) -> list[HybridCandidate]:
    if not candidates or top_k <= 0:
        return []

    reranker = get_reranker_model()

    pairs = [
        (
            query,
            build_candidate_context(candidate),
        )
        for candidate in candidates
    ]

    model_scores = reranker.predict(
        pairs,
        show_progress_bar=False,
    )

    scored_candidates: list[
        tuple[HybridCandidate, float]
    ] = []

    for candidate, model_score in zip(
        candidates,
        model_scores,
    ):
        metadata_score = calculate_metadata_alignment(
            query=query,
            candidate=candidate,
        )

        content_alignment = calculate_content_alignment(
            query=query,
            candidate=candidate,
        )

        final_score = (
            MODEL_WEIGHT * float(model_score)
            + METADATA_WEIGHT * metadata_score
        )

        updated_candidate = candidate.model_copy(
            update={
                "rerank_score": final_score,
            }
        )

        scored_candidates.append(
            (
                updated_candidate,
                content_alignment,
            )
        )

    scored_candidates.sort(
        key=lambda item: item[0].rerank_score or 0.0,
        reverse=True,
    )

    accepted_candidates = [
        candidate
        for candidate, content_alignment in scored_candidates
        if (candidate.rerank_score or 0.0) >= MIN_RERANK_SCORE
        and content_alignment >= MIN_CONTENT_ALIGNMENT
    ]

    if not accepted_candidates:
        fallback_candidates = [
            candidate
            for candidate, content_alignment in scored_candidates
            if (
                (candidate.rerank_score or 0.0)
                >= FALLBACK_MIN_RERANK_SCORE
            )
            and content_alignment
            >= FALLBACK_MIN_CONTENT_ALIGNMENT
        ]

        if fallback_candidates:
            accepted_candidates = [fallback_candidates[0]]

    return limit_evidences_per_technology(
        candidates=accepted_candidates,
        top_k=top_k,
    )