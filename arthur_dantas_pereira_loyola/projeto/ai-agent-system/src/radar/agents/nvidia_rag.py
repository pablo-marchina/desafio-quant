from __future__ import annotations

import unicodedata
from typing import Any, cast, get_args

from radar.graph.progress import get_tracker
from radar.graph.state import RadarState
from radar.rag.knowledge_base import NVIDIA_KNOWLEDGE_CHUNKS
from radar.rag.retriever import ensure_seeded, retrieve
from radar.schemas import NvidiaKnowledgeChunk
from radar.schemas.recommendation import NvidiaTechnology


NVIDIA_TECHNOLOGIES: set[str] = set(get_args(NvidiaTechnology))

# Each hint maps keywords → list of knowledge chunk IDs
QUERY_HINTS: tuple[tuple[tuple[str, ...], str, list[int]], ...] = (
    (
        ("saude", "health", "healthcare", "medical", "medico", "clinica", "clinical"),
        "healthcare medical clinical NVIDIA Clara",
        [14],
    ),
    (
        ("voz", "voice", "speech", "audio", "transcricao", "asr", "tts", "call center", "atendimento"),
        "voice speech ASR TTS transcription NVIDIA Riva",
        [11],
    ),
    (
        ("llm", "generativa", "generative", "chatbot", "assistente", "assistant"),
        "generative AI LLM NVIDIA NIM NVIDIA NeMo NeMo Guardrails TensorRT-LLM",
        [2, 3, 4, 6],
    ),
    (
        ("agente", "agents", "agent", "workflow", "guardrail", "governanca", "governance"),
        "AI agents workflow governance NeMo Guardrails",
        [4],
    ),
    (
        ("latencia", "latency", "inferencia", "inference", "serving", "producao", "production"),
        "production inference serving latency Triton TensorRT-LLM",
        [5, 6],
    ),
    (
        ("dados", "data", "analytics", "tabular", "etl", "pipeline"),
        "data analytics dataframe ETL NVIDIA RAPIDS cuDF cuML",
        [7, 8, 9],
    ),
    (
        ("robo", "robot", "robotica", "robotics", "simulacao", "simulation"),
        "robotics simulation autonomy NVIDIA Isaac NVIDIA Omniverse",
        [12, 13],
    ),
    (
        ("seguranca", "security", "cyber", "cybersecurity"),
        "cybersecurity threat detection NVIDIA Morpheus",
        [15],
    ),
)

_chunks_by_id: dict[int, dict[str, Any]] = {
    c["id"]: c for c in NVIDIA_KNOWLEDGE_CHUNKS
}

HINT_MAP_INDEX: list[tuple[tuple[str, ...], list[int]]] = [
    (needles, chunk_ids) for needles, _, chunk_ids in QUERY_HINTS
]


def retrieve_nvidia_context(state: RadarState) -> list[NvidiaKnowledgeChunk]:
    classification = state.get("classification")
    if not classification or classification.label == "Non-AI":
        return []

    validation = state.get("validation")
    if not validation or not validation.has_minimum_evidence:
        return []

    profiles = state.get("extracted_startups", [])
    if not profiles:
        return []

    profile = profiles[0]
    query_parts = []
    if profile.sector:
        query_parts.append(f"sector: {profile.sector}")
    if profile.product:
        query_parts.append(f"product: {profile.product}")
    if profile.cited_technologies:
        query_parts.append(f"technologies: {', '.join(profile.cited_technologies)}")
    if profile.ai_usage_summary:
        query_parts.append(f"ai_usage: {profile.ai_usage_summary}")

    supported_claims = [
        claim
        for claim in state.get("claims", [])
        if claim.id in validation.supporting_evidence_ids
    ]
    if supported_claims:
        claim_text = " ".join(c.text for c in supported_claims)
        query_parts.append(f"evidence: {claim_text[:1000]}")

    query = " ".join(query_parts) if query_parts else profile.description or ""
    hints = _build_query_hints(query)
    if hints:
        query = f"{query} retrieval_hints: {' '.join(hints)}"
    if not query:
        return []

    tracker = get_tracker()
    if tracker:
        tracker.set_detail("nvidia_rag", "Carregando modelo de embeddings (sentence-transformers)...")
    ensure_seeded()
    if tracker:
        tracker.set_detail("nvidia_rag", "Buscando conhecimento NVIDIA no Qdrant...")
    results = retrieve(query, top_k=8)

    chunks: list[NvidiaKnowledgeChunk] = []
    for result in results:
        score = _as_score(result.get("score"))
        if score < 0.3:
            continue

        technology = _as_nvidia_technology(result.get("technology"))
        if technology is None:
            continue

        chunks.append(
            NvidiaKnowledgeChunk(
                id=str(result.get("id", "")),
                technology=technology,
                title=_as_text(result.get("title")),
                url=_as_text(result.get("url")),
                content=_as_text(result.get("content")),
                relevance_score=score,
            )
        )

    if not chunks:
        chunks = _deterministic_retrieve(query)

    if tracker:
        tracker.set_detail(
            "nvidia_rag",
            f"Encontrados {len(chunks)} chunks NVIDIA relevantes"
        )

    return chunks


def _build_query_hints(text: str) -> list[str]:
    normalized = _normalize_for_hints(text)
    hints: list[str] = []
    for needles, hint, _ in QUERY_HINTS:
        if any(needle in normalized for needle in needles):
            hints.append(hint)
    return hints


def _get_matched_chunk_ids(text: str) -> set[int]:
    normalized = _normalize_for_hints(text)
    matched: set[int] = set()
    for needles, chunk_ids in HINT_MAP_INDEX:
        if any(needle in normalized for needle in needles):
            matched.update(chunk_ids)
    return matched


def _deterministic_retrieve(query: str) -> list[NvidiaKnowledgeChunk]:
    chunk_ids = _get_matched_chunk_ids(query)
    if not chunk_ids:
        return []
    chunks: list[NvidiaKnowledgeChunk] = []
    for cid in chunk_ids:
        raw = _chunks_by_id.get(cid)
        if raw is None:
            continue
        technology = _as_nvidia_technology(raw.get("technology"))
        if technology is None:
            continue
        chunks.append(
            NvidiaKnowledgeChunk(
                id=str(raw["id"]),
                technology=technology,
                title=_as_text(raw.get("title")),
                url=_as_text(raw.get("url")),
                content=_as_text(raw.get("content")),
                relevance_score=0.5,
            )
        )
    return chunks


def _normalize_for_hints(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _as_score(value: Any) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(float(value), 1.0))
    return 0.0


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _as_nvidia_technology(value: Any) -> NvidiaTechnology | None:
    if isinstance(value, str) and value in NVIDIA_TECHNOLOGIES:
        return cast(NvidiaTechnology, value)
    return None