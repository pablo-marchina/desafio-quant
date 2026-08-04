"""Repositorio estatico do catalogo NVIDIA Knowledge V1."""

from apps.api.src.modules.nvidia_knowledge.domain.entities import NvidiaTechnology
from apps.api.src.modules.nvidia_knowledge.domain.enums import (
    NvidiaTechnologyCategory,
)
from apps.api.src.modules.nvidia_knowledge.domain.repositories import (
    NvidiaTechnologyRepository,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.catalog_data import (
    INITIAL_NVIDIA_TECHNOLOGIES,
)


class StaticNvidiaTechnologyRepository(NvidiaTechnologyRepository):
    """Repositorio em memoria com o catalogo inicial versionado em codigo."""

    def __init__(
        self,
        technologies: tuple[NvidiaTechnology, ...] = INITIAL_NVIDIA_TECHNOLOGIES,
    ) -> None:
        self._technologies = tuple(sorted(technologies, key=lambda item: item.name))
        self._by_slug = {technology.slug: technology for technology in technologies}

    async def list_all(
        self,
        *,
        category: NvidiaTechnologyCategory | None = None,
        query: str | None = None,
    ) -> list[NvidiaTechnology]:
        results = list(self._technologies)
        if category is not None:
            results = [
                technology
                for technology in results
                if technology.category == category
            ]
        if query:
            results = [
                technology
                for technology in results
                if technology.matches_query(query)
            ]
        return results

    async def get_by_slug(self, slug: str) -> NvidiaTechnology | None:
        return self._by_slug.get(slug.strip().lower())
