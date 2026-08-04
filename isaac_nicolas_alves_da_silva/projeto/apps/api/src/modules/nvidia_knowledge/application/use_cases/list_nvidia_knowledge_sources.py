"""Caso de uso para listar fontes NVIDIA Knowledge V2."""

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaKnowledgeSourcesInput,
    NvidiaKnowledgeSourceView,
)
from apps.api.src.modules.nvidia_knowledge.application.public.source_registry import (
    NvidiaKnowledgeSourceRegistry,
)
from apps.api.src.modules.nvidia_knowledge.domain.entities import (
    NvidiaKnowledgeSource,
)
from apps.api.src.modules.nvidia_knowledge.domain.repositories import (
    NvidiaKnowledgeSourceRepository,
)


def source_to_view(source: NvidiaKnowledgeSource) -> NvidiaKnowledgeSourceView:
    return NvidiaKnowledgeSourceView(
        slug=source.slug,
        title=source.title,
        url=source.url,
        source_type=source.source_type,
        priority=source.priority,
        technology_slug=source.technology_slug,
        description=source.description,
        tags=list(source.tags),
    )


class ListNvidiaKnowledgeSources(NvidiaKnowledgeSourceRegistry):
    """Lista fontes planejadas para ingestao do NVIDIA Knowledge V2."""

    def __init__(self, repository: NvidiaKnowledgeSourceRepository) -> None:
        self._repository = repository

    async def list_sources(
        self,
        registry_input: ListNvidiaKnowledgeSourcesInput,
    ) -> list[NvidiaKnowledgeSourceView]:
        sources = await self._repository.list_all(
            priority=registry_input.priority,
            technology_slug=registry_input.technology_slug,
            query=registry_input.query,
        )
        return [source_to_view(source) for source in sources]

    async def execute(
        self,
        registry_input: ListNvidiaKnowledgeSourcesInput,
    ) -> list[NvidiaKnowledgeSourceView]:
        return await self.list_sources(registry_input)
