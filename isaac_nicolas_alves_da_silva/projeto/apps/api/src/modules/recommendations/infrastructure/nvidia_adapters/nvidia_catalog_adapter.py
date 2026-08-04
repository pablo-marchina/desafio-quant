"""Adaptador que liga recommendations ao contrato publico do modulo nvidia_knowledge.

Esta e a UNICA peca do modulo ``recommendations`` que conhece o modulo
``nvidia_knowledge`` — e mesmo assim, conhece apenas o contrato publico
(``nvidia_knowledge/application/public/technology_catalog.py``).
"""

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaTechnologiesInput,
)
from apps.api.src.modules.nvidia_knowledge.application.public.technology_catalog import (
    NvidiaTechnologyCatalog,
)
from apps.api.src.modules.recommendations.application.dto import (
    NvidiaTechnologySnapshot,
)
from apps.api.src.modules.recommendations.application.ports import (
    NvidiaCatalogSource,
)


class NvidiaKnowledgeCatalogAdapter(NvidiaCatalogSource):
    """Implementa ``NvidiaCatalogSource`` chamando o modulo nvidia_knowledge."""

    def __init__(self, catalog: NvidiaTechnologyCatalog) -> None:
        self._catalog = catalog

    async def list_technologies(self) -> list[NvidiaTechnologySnapshot]:
        technologies = await self._catalog.list_technologies(
            ListNvidiaTechnologiesInput()
        )
        return [
            NvidiaTechnologySnapshot(
                slug=technology.slug,
                name=technology.name,
                category=technology.category.value,
                use_cases=tuple(technology.use_cases),
                keywords=tuple(technology.keywords),
                complexity=technology.complexity,
                supported_workloads=dict(technology.supported_workloads),
            )
            for technology in technologies
        ]
