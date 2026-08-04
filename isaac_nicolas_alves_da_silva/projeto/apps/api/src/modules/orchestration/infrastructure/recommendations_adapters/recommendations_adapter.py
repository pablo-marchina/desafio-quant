"""Adaptador que liga orchestration ao contrato publico do modulo
recommendations (e, quando disponivel, ao Recommendation Agent V11 de
``agents``).

Esta e a UNICA peca do modulo ``orchestration`` que conhece os modulos
``recommendations``/``agents`` para este fluxo — e mesmo assim, conhece
apenas os contratos publicos
(``recommendations/application/public/recommendation_generator.py``,
``agents/application/public/recommendation_agent.py``). A traducao do
``StartupProfileUnavailableError`` (vocabulario de recommendations) para o
``StartupProfileUnavailableError`` de orchestration acontece somente aqui.
"""

from uuid import UUID

from apps.api.src.modules.agents.application.dto import RecommendationAgentInput
from apps.api.src.modules.agents.application.public.recommendation_agent import (
    RecommendationAgentService,
)
from apps.api.src.modules.orchestration.application.ports import (
    RecommendationsPort,
)
from apps.api.src.modules.orchestration.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.modules.recommendations.application.public.recommendation_generator import (
    RecommendationGenerator,
)
from apps.api.src.modules.recommendations.domain.exceptions import (
    StartupProfileUnavailableError as RecommendationsStartupProfileUnavailableError,
)


class RecommendationsModulePort(RecommendationsPort):
    """Implementa ``RecommendationsPort`` chamando o modulo recommendations.

    Quando ``agent_service`` esta disponivel (``GEMINI_API_KEY``
    configurada), usa o Recommendation Agent V11 — que ja chama o gerador
    determinístico como tool e persiste a justificativa revisada de volta
    em ``recommendations`` antes de devolver. Sem a chave, cai para o
    gerador V1 puro, comportamento identico ao de antes desta entrega.
    """

    def __init__(
        self,
        generator: RecommendationGenerator,
        agent_service: RecommendationAgentService | None = None,
    ) -> None:
        self._generator = generator
        self._agent_service = agent_service

    async def generate(self, startup_id: UUID) -> int:
        try:
            if self._agent_service is not None:
                result = await self._agent_service.recommend(
                    RecommendationAgentInput(startup_id=startup_id)
                )
                return len(result.recommendations)

            recommendations = await self._generator.generate(startup_id)
        except RecommendationsStartupProfileUnavailableError as error:
            raise StartupProfileUnavailableError(str(error)) from error

        return len(recommendations)
