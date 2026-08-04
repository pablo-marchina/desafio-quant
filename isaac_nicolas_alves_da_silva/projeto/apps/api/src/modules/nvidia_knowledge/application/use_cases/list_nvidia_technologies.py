"""Caso de uso para listar tecnologias NVIDIA."""

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaTechnologiesInput,
    NvidiaTechnologyView,
)
from apps.api.src.modules.nvidia_knowledge.application.public.technology_catalog import (
    NvidiaTechnologyCatalog,
)
from apps.api.src.modules.nvidia_knowledge.domain.entities import NvidiaTechnology
from apps.api.src.modules.nvidia_knowledge.domain.exceptions import (
    NvidiaTechnologyNotFoundError,
)
from apps.api.src.modules.nvidia_knowledge.domain.repositories import (
    NvidiaTechnologyRepository,
)


def technology_to_view(technology: NvidiaTechnology) -> NvidiaTechnologyView:
    return NvidiaTechnologyView(
        slug=technology.slug,
        name=technology.name,
        category=technology.category,
        description=technology.description,
        use_cases=list(technology.use_cases),
        keywords=list(technology.keywords),
        official_url=technology.official_url,
        complexity=technology.complexity,
        supported_workloads=dict(technology.supported_workloads),
    )


class ListNvidiaTechnologies(NvidiaTechnologyCatalog):
    """Lista e consulta tecnologias do catalogo inicial."""

    def __init__(self, repository: NvidiaTechnologyRepository) -> None:
        self._repository = repository

    async def list_technologies(
        self,
        catalog_input: ListNvidiaTechnologiesInput,
    ) -> list[NvidiaTechnologyView]:
        technologies = await self._repository.list_all(
            category=catalog_input.category,
            query=catalog_input.query,
        )
        return [technology_to_view(technology) for technology in technologies]

    async def get_technology(self, slug: str) -> NvidiaTechnologyView:
        technology = await self._repository.get_by_slug(slug)
        if technology is None:
            raise NvidiaTechnologyNotFoundError(
                f"Tecnologia NVIDIA nao encontrada: {slug}."
            )
        return technology_to_view(technology)

    async def execute(
        self,
        catalog_input: ListNvidiaTechnologiesInput,
    ) -> list[NvidiaTechnologyView]:
        return await self.list_technologies(catalog_input)
