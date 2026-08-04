from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_+\-.]+")

STOPWORDS = {
    "a",
    "as",
    "and",
    "ao",
    "aos",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "for",
    "in",
    "na",
    "nas",
    "no",
    "nos",
    "of",
    "on",
    "or",
    "para",
    "por",
    "the",
    "to",
    "um",
    "uma",
    "with",
}

DOMAIN_RULES = [
    (
        ("saude", "health", "healthcare", "clinico", "clinica", "medico", "medical"),
        ("clara", "ai enterprise", "guardrails", "nim"),
        0.34,
    ),
    (
        ("llm", "inferencia", "inference", "latencia", "latency", "api externa", "deploy"),
        ("nim", "tensorrt-llm", "triton", "dynamo", "api catalog"),
        0.32,
    ),
    (
        ("governanca", "governance", "guardrails", "seguranca", "safety", "agente"),
        ("guardrails", "nemo", "ai enterprise", "nemotron"),
        0.28,
    ),
    (
        ("agent", "agente", "workflow", "rag", "assistant", "assistente", "copilot"),
        ("blueprints", "nemo", "nemotron", "api catalog", "nim"),
        0.3,
    ),
    (
        ("modelo aberto", "open model", "foundation model", "reasoning", "raciocinio", "coding"),
        ("nemotron", "api catalog", "nemo"),
        0.3,
    ),
    (
        ("dados", "tabular", "pandas", "etl", "analytics", "machine learning"),
        ("rapids", "cudf", "cuml"),
        0.3,
    ),
    (
        ("logistica", "logistics", "rota", "routing", "scheduling", "otimizacao", "optimization"),
        ("cuopt",),
        0.62,
    ),
    (
        ("ambiente", "environment", "reprodutivel", "reproducible", "container", "sdk"),
        ("ai workbench", "ngc"),
        0.26,
    ),
    (
        ("voz", "speech", "call center", "transcricao", "asr", "tts"),
        ("riva", "nim", "triton"),
        0.3,
    ),
    (
        ("robotica", "robotics", "simulacao", "simulation", "digital twin", "physical ai"),
        ("isaac", "omniverse", "cuda", "cosmos"),
        0.3,
    ),
    (
        ("cyber", "seguranca", "security", "fraud", "anomalia", "threat"),
        ("morpheus", "cudf"),
        0.32,
    ),
    (
        ("startup", "go-to-market", "comunidade", "suporte tecnico"),
        ("inception",),
        0.24,
    ),
]


def normalize_text(text: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def tokenize(text: object) -> list[str]:
    return [
        token
        for token in TOKEN_PATTERN.findall(normalize_text(text))
        if len(token) > 2 and token not in STOPWORDS
    ]


def payload_text(payload: dict[str, Any]) -> str:
    return " ".join(
        str(payload.get(key) or "")
        for key in ("product_name", "category", "summary", "chunk_text")
    )


def recommendation_boost(product_name: str, category: str, profile_text: str) -> float:
    text = normalize_text(profile_text)
    product = normalize_text(product_name)
    category = normalize_text(category)
    boost = 0.0

    for terms, products, value in DOMAIN_RULES:
        if any(term in text for term in terms) and any(
            target in product or target in category for target in products
        ):
            boost += value

    return boost


def lexical_overlap_score(query: str, document_text: str) -> float:
    query_terms = set(tokenize(query))
    document_terms = set(tokenize(document_text))
    if not query_terms or not document_terms:
        return 0.0

    overlap = query_terms & document_terms
    recall = len(overlap) / len(query_terms)
    precision = len(overlap) / len(document_terms)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def bm25_scores(
    query: str,
    documents: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    query_terms = tokenize(query)
    tokenized_documents = [tokenize(document) for document in documents]
    if not query_terms or not tokenized_documents:
        return [0.0 for _document in documents]

    document_count = len(tokenized_documents)
    average_length = (
        sum(len(document_terms) for document_terms in tokenized_documents)
        / max(1, document_count)
    ) or 1.0
    document_frequency: dict[str, int] = {}
    for term in set(query_terms):
        document_frequency[term] = sum(
            1 for document_terms in tokenized_documents if term in document_terms
        )

    scores: list[float] = []
    for document_terms in tokenized_documents:
        term_frequency: dict[str, int] = {}
        for term in document_terms:
            term_frequency[term] = term_frequency.get(term, 0) + 1

        document_length = len(document_terms) or 1
        score = 0.0
        for term in query_terms:
            frequency = term_frequency.get(term, 0)
            if frequency == 0:
                continue
            frequency_in_documents = document_frequency.get(term, 0)
            idf = math.log(
                1
                + (document_count - frequency_in_documents + 0.5)
                / (frequency_in_documents + 0.5)
            )
            denominator = frequency + k1 * (
                1 - b + b * document_length / average_length
            )
            score += idf * (frequency * (k1 + 1)) / denominator
        scores.append(score)
    return scores


def phrase_score(query: str, document_text: str) -> float:
    normalized_query = normalize_text(query)
    normalized_document = normalize_text(document_text)
    phrases = [
        phrase
        for phrase in re.split(r"[,.;:\n]", normalized_query)
        if len(phrase.strip()) >= 8
    ]
    direct_hits = sum(1 for phrase in phrases if phrase.strip() in normalized_document)
    return min(1.0, direct_hits * 0.25)


def source_quality_score(payload: dict[str, Any]) -> float:
    source_type = normalize_text(payload.get("source_type") or "")
    source_url = normalize_text(payload.get("source_url") or "")
    if "official" in source_type or "nvidia.com" in source_url or "docs.nvidia.com" in source_url:
        return 1.0
    if "seed" in source_type:
        return 0.75
    return 0.5


def normalize_vector_score(score: float) -> float:
    if score <= 0:
        return 0.0
    if score <= 1:
        return score
    return 1 - math.exp(-score)


def min_max_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high == low:
        return [0.5 for _ in values]
    return [(value - low) / (high - low) for value in values]


@lru_cache(maxsize=2)
def load_cross_encoder(model_name: str, local_files_only: bool):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name, local_files_only=local_files_only)


def cross_encoder_scores(
    query: str,
    candidates: list[str],
    *,
    model_name: str,
    local_files_only: bool,
) -> list[float] | None:
    if not candidates:
        return []
    try:
        model = load_cross_encoder(model_name, local_files_only)
        scores = model.predict([(query, candidate) for candidate in candidates])
    except Exception:
        return None
    return [float(score) for score in scores]


def rerank_results(
    results: list[dict[str, Any]],
    query: str,
    *,
    provider: str = "hybrid",
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    cross_encoder_local_files_only: bool = True,
) -> list[dict[str, Any]]:
    scored = []
    document_texts = []
    for result in results:
        payload = result.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        document_text = payload_text(payload)
        document_texts.append(document_text)
        vector = normalize_vector_score(float(result.get("score") or 0.0))
        lexical = lexical_overlap_score(query, document_text)
        phrase = phrase_score(query, document_text)
        domain = recommendation_boost(
            str(payload.get("product_name", "")),
            str(payload.get("category", "")),
            query,
        )
        quality = source_quality_score(payload)
        scored.append(
            {
                "result": result,
                "vector_score": vector,
                "lexical_score": lexical,
                "bm25_score": 0.0,
                "phrase_score": phrase,
                "domain_score": domain,
                "source_quality_score": quality,
                "cross_encoder_score": None,
            }
        )

    normalized_bm25_scores = min_max_normalize(bm25_scores(query, document_texts))
    for index, item in enumerate(scored):
        item["bm25_score"] = normalized_bm25_scores[index] if normalized_bm25_scores else 0.0

    cross_scores = None
    if provider in {"cross_encoder", "cross-encoder"}:
        cross_scores = cross_encoder_scores(
            query,
            document_texts,
            model_name=cross_encoder_model,
            local_files_only=cross_encoder_local_files_only,
        )

    normalized_cross_scores = min_max_normalize(cross_scores) if cross_scores else []
    for index, item in enumerate(scored):
        if normalized_cross_scores:
            cross = normalized_cross_scores[index]
            final = (
                item["vector_score"] * 0.3
                + cross * 0.38
                + item["bm25_score"] * 0.1
                + item["lexical_score"] * 0.07
                + item["phrase_score"] * 0.03
                + item["domain_score"] * 0.1
                + item["source_quality_score"] * 0.02
            )
            item["cross_encoder_score"] = cross_scores[index]
        else:
            final = (
                item["vector_score"] * 0.46
                + item["bm25_score"] * 0.14
                + item["lexical_score"] * 0.08
                + item["phrase_score"] * 0.07
                + item["domain_score"] * 0.2
                + item["source_quality_score"] * 0.05
            )

        result = dict(item["result"])
        details = {
            "final_score": round(final, 6),
            "vector_score": round(item["vector_score"], 6),
            "bm25_score": round(item["bm25_score"], 6),
            "lexical_score": round(item["lexical_score"], 6),
            "phrase_score": round(item["phrase_score"], 6),
            "domain_score": round(item["domain_score"], 6),
            "source_quality_score": round(item["source_quality_score"], 6),
            "provider": "cross_encoder" if normalized_cross_scores else "hybrid",
        }
        if item["cross_encoder_score"] is not None:
            details["cross_encoder_score"] = round(float(item["cross_encoder_score"]), 6)
        result["rerank_score"] = final
        result["rerank_details"] = details
        item["result"] = result

    return [
        item["result"]
        for item in sorted(scored, key=lambda scored_item: scored_item["result"]["rerank_score"], reverse=True)
    ]
