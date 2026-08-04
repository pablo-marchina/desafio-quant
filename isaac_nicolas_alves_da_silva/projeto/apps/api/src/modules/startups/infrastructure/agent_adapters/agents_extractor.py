"""Adaptador que liga o startups ao contrato publico do modulo agents.

Esta e a UNICA peca do modulo ``startups`` que conhece o Extraction Agent
de ``agents`` — e mesmo assim, conhece apenas o contrato publico
(``agents/application/public/extractor.py``). Nenhum node, grafo ou
prompt interno de ``agents`` e importado aqui.

Responsabilidade desta classe:

```txt
implementar a porta ExtractionPort (startups/application/ports.py)
traduzir os campos da startup -> ExtractionInput (agents)
traduzir ExtractionResult (agents) -> ExtractionOutcome (startups)
```

Cada modulo mantem seu proprio vocabulario (enums e DTOs). Esta classe e o
unico lugar onde os dois vocabularios se encontram.
"""

from datetime import UTC, datetime

from apps.api.src.modules.agents.application.dto import ExtractionInput
from apps.api.src.modules.agents.application.public.extractor import (
    ExtractionService,
)
from apps.api.src.modules.startups.application.ports import (
    ExtractionOutcome,
    ExtractionPort,
)
from apps.api.src.modules.startups.domain.entities import StartupAIProfile
from apps.api.src.modules.startups.domain.enums import (
    AiDataModality,
    AiDeploymentStage,
    AiGpuNeed,
    AiInfraEnvironment,
    AiLatencyRequirement,
    AiModelType,
    AiWorkloadType,
    FundingStage,
)


def _safe_enum(enum_cls, value: str, default):
    """Converte string para enum; retorna default quando o valor e invalido."""
    try:
        return enum_cls(value)
    except ValueError:
        return default


_MAIN_FIELD_NAMES = frozenset(
    {
        "founders",
        "funding_stage",
        "funding_amount_usd",
        "customers",
        "sector",
        "description",
        "country",
    }
)


class AgentsExtractor(ExtractionPort):
    """Implementa ``ExtractionPort`` chamando o modulo agents."""

    def __init__(self, extraction_service: ExtractionService) -> None:
        self.extraction_service = extraction_service

    async def extract(
        self,
        *,
        name: str,
        sector: str | None,
        description: str | None,
        evidence_texts: list[str],
    ) -> ExtractionOutcome:
        """Traduz a entrada, chama o agente e traduz a saida de volta."""

        agents_input = ExtractionInput(
            name=name,
            sector=sector,
            description=description,
            evidence_texts=evidence_texts,
        )
        r = await self.extraction_service.extract(agents_input)

        # Os dois enums (``agents.ExtractedFundingStage`` e
        # ``startups.FundingStage``) compartilham os mesmos valores de
        # string, de proposito, para que esta traducao seja so uma troca
        # de tipo.
        funding_stage = FundingStage(r.funding_stage.value)

        # Separa confianca por dominio: chaves de campos basicos ficam em
        # ExtractionOutcome.field_confidence; chaves de perfil de IA ficam
        # em StartupAIProfile.field_confidence.
        main_confidence = {k: v for k, v in r.field_confidence.items() if k in _MAIN_FIELD_NAMES}
        ai_profile_confidence = {k: v for k, v in r.field_confidence.items() if k not in _MAIN_FIELD_NAMES}
        main_evidence_ids = {
            k: v for k, v in r.field_evidence_ids.items() if k in _MAIN_FIELD_NAMES
        }
        ai_profile_evidence_ids = {
            k: v for k, v in r.field_evidence_ids.items() if k not in _MAIN_FIELD_NAMES
        }

        ai_profile = StartupAIProfile(
            ai_workload_type=_safe_enum(AiWorkloadType, r.ai_workload_type, AiWorkloadType.UNKNOWN),
            model_type=_safe_enum(AiModelType, r.model_type, AiModelType.UNKNOWN),
            data_modality=_safe_enum(AiDataModality, r.data_modality, AiDataModality.UNKNOWN),
            deployment_stage=_safe_enum(AiDeploymentStage, r.deployment_stage, AiDeploymentStage.UNKNOWN),
            infra_environment=_safe_enum(AiInfraEnvironment, r.infra_environment, AiInfraEnvironment.UNKNOWN),
            gpu_need=_safe_enum(AiGpuNeed, r.gpu_need, AiGpuNeed.UNKNOWN),
            latency_requirement=_safe_enum(AiLatencyRequirement, r.latency_requirement, AiLatencyRequirement.UNKNOWN),
            scale_signal=r.scale_signal,
            current_tools=tuple(r.current_tools),
            business_goal=r.business_goal,
            field_confidence=ai_profile_confidence,
            field_evidence_ids=ai_profile_evidence_ids,
            extracted_at=datetime.now(UTC),
        )

        return ExtractionOutcome(
            founders=r.founders,
            funding_stage=funding_stage,
            funding_amount_usd=r.funding_amount_usd,
            customers=r.customers,
            sector=r.sector,
            description=r.description,
            country=r.country,
            ai_profile=ai_profile,
            field_confidence=main_confidence,
            field_evidence_ids=main_evidence_ids,
        )
