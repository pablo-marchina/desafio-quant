"""Adaptador que liga orchestration ao contrato publico do modulo briefing
(e, quando disponivel, ao Briefing Agent V12 de ``agents``).

Esta e a UNICA peca do modulo ``orchestration`` que conhece os modulos
``briefing``/``agents`` para este fluxo — e mesmo assim, conhece apenas os
contratos publicos (``briefing/application/public/briefing_generator.py``,
``agents/application/public/briefing_agent.py``).
"""

import asyncio
from uuid import UUID

from apps.api.src.modules.agents.application.dto import BriefingAgentInput
from apps.api.src.modules.agents.application.public.briefing_agent import (
    BriefingAgentService,
)
from apps.api.src.modules.briefing.application.public.briefing_generator import (
    BriefingGenerator,
)
from apps.api.src.modules.briefing.domain.exceptions import (
    StartupProfileUnavailableError as BriefingStartupProfileUnavailableError,
)
from apps.api.src.modules.orchestration.application.ports import BriefingPort
from apps.api.src.modules.orchestration.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.shared.logging import get_logger


logger = get_logger(__name__)
BRIEFING_AGENT_TIMEOUT_SECONDS = 45


class BriefingModulePort(BriefingPort):
    """Implementa ``BriefingPort`` chamando o modulo briefing.

    Quando ``agent_service`` esta disponivel (``GEMINI_API_KEY``
    configurada), usa o Briefing Agent V12 — que ja chama o gerador
    determinístico como tool e persiste a prosa revisada de volta em
    ``briefing`` antes de devolver. Sem a chave, cai para o gerador V1
    puro, comportamento identico ao de antes desta entrega.
    """

    def __init__(
        self,
        generator: BriefingGenerator,
        agent_service: BriefingAgentService | None = None,
    ) -> None:
        self._generator = generator
        self._agent_service = agent_service

    async def generate(self, startup_id: UUID) -> UUID:
        try:
            if self._agent_service is not None:
                try:
                    result = await asyncio.wait_for(
                        self._agent_service.generate(
                            BriefingAgentInput(startup_id=startup_id)
                        ),
                        timeout=BRIEFING_AGENT_TIMEOUT_SECONDS,
                    )
                    return result.briefing_id
                except Exception as error:
                    logger.warning(
                        "briefing agent failed, falling back to deterministic generator",
                        extra={"startup_id": str(startup_id), "reason": str(error)},
                    )

            briefing = await self._generator.generate(startup_id)
        except BriefingStartupProfileUnavailableError as error:
            raise StartupProfileUnavailableError(str(error)) from error

        return briefing.id
