"""Evidencias suplementares do catalogo curado NVIDIA Knowledge."""

from uuid import NAMESPACE_URL, uuid5

from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.catalog_data import (
    INITIAL_NVIDIA_TECHNOLOGIES,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.source_data import (
    INITIAL_NVIDIA_KNOWLEDGE_SOURCES,
)
from apps.api.src.modules.rag.application.dto import EvidenceChunkView
from apps.api.src.modules.rag.application.ports import SupplementalEvidenceProvider

NVIDIA_KNOWLEDGE_SOURCE_TYPE = "nvidia_knowledge"

_ALIASES_BY_TECHNOLOGY_SLUG: dict[str, tuple[str, ...]] = {
    "nvidia-nemo": ("nvidia nemo", "nemo framework", "nemo"),
    "nemo-guardrails": ("nemo guardrails", "guardrails"),
    "triton-inference-server": (
        "nvidia triton inference server",
        "triton inference server",
        "triton",
    ),
    "tensorrt-llm": ("tensorrt-llm", "tensorrt llm"),
    "tensorrt": ("nvidia tensorrt", "tensorrt"),
    "riva": ("nvidia riva", "riva"),
    "nvidia-ai-enterprise": ("nvidia ai enterprise", "ai enterprise"),
    "nvidia-inception": ("nvidia inception", "inception program", "inception"),
    "nvidia-morpheus": ("nvidia morpheus", "morpheus"),
    "cudf": ("cudf",),
    "cuml": ("cuml",),
    "nvidia-clara": ("nvidia clara", "clara"),
}


class StaticNvidiaKnowledgeEvidenceProvider(SupplementalEvidenceProvider):
    """Busca evidencias curadas quando a query menciona tecnologia conhecida."""

    def __init__(self) -> None:
        self._sources_by_technology_slug = {
            source.technology_slug: source
            for source in INITIAL_NVIDIA_KNOWLEDGE_SOURCES
            if source.technology_slug is not None
        }

    async def find(
        self,
        query: str,
        *,
        source_type: str | None = None,
        limit: int,
    ) -> list[EvidenceChunkView]:
        if source_type != NVIDIA_KNOWLEDGE_SOURCE_TYPE:
            return []

        normalized_query = query.lower()
        matches = [
            (self._score(normalized_query, technology.slug), technology)
            for technology in INITIAL_NVIDIA_TECHNOLOGIES
        ]
        ranked = [
            (score, technology)
            for score, technology in matches
            if score > 0
        ]
        ranked.sort(key=lambda item: item[0], reverse=True)

        return [
            self._to_evidence(technology, score)
            for score, technology in ranked[:limit]
        ]

    def _score(self, normalized_query: str, technology_slug: str) -> float:
        aliases = _ALIASES_BY_TECHNOLOGY_SLUG.get(
            technology_slug, (technology_slug.replace("-", " "),)
        )
        score = 0.0
        for alias in aliases:
            if alias in normalized_query:
                score = max(score, len(alias) / 100.0)
        return score

    def _to_evidence(self, technology, score: float) -> EvidenceChunkView:
        source = self._sources_by_technology_slug.get(technology.slug)
        source_description = source.description if source is not None else ""
        source_tags = ", ".join(source.tags) if source is not None else ""
        text = (
            f"{technology.name}\n"
            f"Description: {technology.description}\n"
            f"Use cases: {'; '.join(technology.use_cases)}.\n"
            f"Keywords: {', '.join(technology.keywords)}.\n"
            f"Official source summary: {source_description}\n"
            f"Source tags: {source_tags}"
        )
        evidence_id = uuid5(NAMESPACE_URL, f"nvidia-knowledge:{technology.slug}")
        return EvidenceChunkView(
            chunk_id=evidence_id,
            document_id=evidence_id,
            source_url=technology.official_url,
            text=text,
            score=1.0 + score,
            source_type=NVIDIA_KNOWLEDGE_SOURCE_TYPE,
        )
