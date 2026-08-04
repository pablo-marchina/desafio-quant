"""Adaptador que implementa BriefingToolPort usando o contrato publico
de ``briefing``.

Nao importa nada de ``briefing`` alem de ``application/public/`` — as
instancias de ``BriefingGenerator`` e ``BriefingContentUpdater`` sao
construidas pela ``BriefingFactory`` e injetadas aqui.
"""

from uuid import UUID

from apps.api.src.modules.agents.application.ports import BriefingToolPort
from apps.api.src.modules.agents.domain.exceptions import AgentBriefingError
from apps.api.src.modules.briefing.application.public.briefing_content_updater import (
    BriefingContentUpdater,
)
from apps.api.src.modules.briefing.application.public.briefing_generator import (
    BriefingGenerator,
)
from apps.api.src.modules.briefing.domain.exceptions import BriefingError


class BriefingGeneratorAdapter(BriefingToolPort):

    def __init__(
        self,
        generator: BriefingGenerator,
        content_updater: BriefingContentUpdater,
    ) -> None:
        self._generator = generator
        self._content_updater = content_updater

    async def generate(self, startup_id: UUID) -> str:
        try:
            view = await self._generator.generate(startup_id)
        except BriefingError as error:
            raise AgentBriefingError(
                f"Geracao de briefing falhou: {error}"
            ) from error

        return view.content

    async def update_content(self, startup_id: UUID, content: str) -> UUID:
        try:
            return await self._content_updater.update_content(startup_id, content)
        except BriefingError as error:
            raise AgentBriefingError(
                f"Atualizacao de conteudo do briefing falhou: {error}"
            ) from error
