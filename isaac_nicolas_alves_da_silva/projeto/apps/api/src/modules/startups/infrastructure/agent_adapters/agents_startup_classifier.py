"""Adaptador que liga o startups ao contrato publico do modulo agents.

Esta e a UNICA peca do modulo ``startups`` que conhece o modulo
``agents`` — e mesmo assim, conhece apenas o contrato publico
(``agents/application/public/startup_classifier.py``). Nenhum node, grafo
ou prompt interno de ``agents`` e importado aqui.

Responsabilidade desta classe:

```txt
implementar a porta StartupClassifierPort (startups/application/ports.py)
traduzir os campos da startup       -> StartupClassificationInput (agents)
traduzir StartupClassificationResult (agents) -> ClassificationOutcome (startups)
```

Cada modulo mantem seu proprio vocabulario (enums e DTOs). Esta classe e o
unico lugar onde os dois vocabularios se encontram.
"""

from apps.api.src.modules.agents.application.dto import StartupClassificationInput
from apps.api.src.modules.agents.application.public.startup_classifier import (
    StartupClassifierService,
)
from apps.api.src.modules.startups.application.ports import (
    ClassificationOutcome,
    StartupClassifierPort,
)
from apps.api.src.modules.startups.domain.enums import AiMaturityLevel
from apps.api.src.modules.startups.domain.policies import calibrate_ai_maturity_level


class AgentsStartupClassifier(StartupClassifierPort):
    """Implementa ``StartupClassifierPort`` chamando o modulo agents."""

    def __init__(self, classification_service: StartupClassifierService) -> None:
        self.classification_service = classification_service

    async def classify(
        self,
        *,
        name: str,
        sector: str | None,
        description: str | None,
        country: str | None,
        website_url: str | None,
        evidence_texts: list[str],
    ) -> ClassificationOutcome:
        """Traduz a entrada, chama o agente e traduz a saida de volta."""

        agents_input = StartupClassificationInput(
            name=name,
            sector=sector,
            description=description,
            country=country,
            website_url=website_url,
            evidence_texts=evidence_texts,
        )
        agents_result = await self.classification_service.classify(agents_input)

        # Os dois enums (``agents.StartupMaturityLevel`` e
        # ``startups.AiMaturityLevel``) compartilham os mesmos valores de
        # string ("ai_native", "ai_enabled", "non_ai"), de proposito, para
        # que esta traducao seja so uma troca de tipo.
        level = AiMaturityLevel(agents_result.level.value)
        level, reason = calibrate_ai_maturity_level(
            level=level,
            reason=agents_result.reason,
            name=name,
            sector=sector,
            description=description,
            website_url=website_url,
            evidence_texts=evidence_texts,
        )

        return ClassificationOutcome(level=level, reason=reason)
