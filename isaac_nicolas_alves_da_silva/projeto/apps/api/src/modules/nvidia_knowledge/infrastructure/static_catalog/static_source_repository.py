"""Repositorio estatico de fontes NVIDIA Knowledge V2."""

from apps.api.src.modules.nvidia_knowledge.domain.entities import (
    NvidiaKnowledgeSource,
)
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaKnowledgeSourcePriority,
)
from apps.api.src.modules.nvidia_knowledge.domain.repositories import (
    NvidiaKnowledgeSourceRepository,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.source_data import (
    INITIAL_NVIDIA_KNOWLEDGE_SOURCES,
)


class StaticNvidiaKnowledgeSourceRepository(NvidiaKnowledgeSourceRepository):
    """Lista fontes planejadas para ingestao da base NVIDIA Knowledge."""

    def __init__(
        self,
        sources: tuple[NvidiaKnowledgeSource, ...] = INITIAL_NVIDIA_KNOWLEDGE_SOURCES,
    ) -> None:
        self._sources = sources

    async def list_all(
        self,
        *,
        priority: NvidiaKnowledgeSourcePriority | None = None,
        technology_slug: str | None = None,
        query: str | None = None,
    ) -> list[NvidiaKnowledgeSource]:
        normalized_slug = technology_slug.strip().lower() if technology_slug else None
        sources = [
            source
            for source in self._sources
            if priority is None or source.priority == priority
        ]
        if normalized_slug is not None:
            sources = [
                source
                for source in sources
                if source.technology_slug == normalized_slug
            ]
        if query:
            sources = [source for source in sources if source.matches_query(query)]
        return sorted(
            sources,
            key=lambda source: (
                source.priority.value,
                source.technology_slug or "",
                source.title,
            ),
        )
