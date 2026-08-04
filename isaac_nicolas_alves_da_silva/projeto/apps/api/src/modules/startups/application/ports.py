"""Portas que conectam a aplicacao de startups a outros modulos.

``startups`` mantem seu proprio vocabulario (``ClassificationOutcome``).
A implementacao concreta desta porta vive em
``infrastructure/agent_adapters/`` e e o unico lugar que conhece o
contrato publico do modulo ``agents``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from apps.api.src.modules.startups.domain.entities import StartupAIProfile
from apps.api.src.modules.startups.domain.enums import AiMaturityLevel, FundingStage


@dataclass(frozen=True)
class ClassificationOutcome:
    """Resultado de classificacao, no vocabulario de startups."""

    level: AiMaturityLevel
    reason: str


class StartupClassifierPort(ABC):
    """Contrato para classificar a maturidade de IA de uma startup."""

    @abstractmethod
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
        """Classifica a startup a partir do perfil e evidencias fornecidos."""


@dataclass(frozen=True)
class ExtractionOutcome:
    """Resultado de extracao, no vocabulario de startups."""

    founders: list[str] = field(default_factory=list)
    funding_stage: FundingStage = FundingStage.UNKNOWN
    funding_amount_usd: float | None = None
    customers: list[str] = field(default_factory=list)
    sector: str | None = None
    description: str | None = None
    country: str | None = None
    ai_profile: StartupAIProfile | None = None
    # Confianca por campo basico (founders, sector, etc.) reportada pelo LLM.
    field_confidence: dict[str, float] = field(default_factory=dict)
    field_evidence_ids: dict[str, list[str]] = field(default_factory=dict)


class ExtractionPort(ABC):
    """Contrato para extrair dados estruturados de uma startup."""

    @abstractmethod
    async def extract(
        self,
        *,
        name: str,
        sector: str | None,
        description: str | None,
        evidence_texts: list[str],
    ) -> ExtractionOutcome:
        """Extrai founders/funding/customers a partir do perfil e evidencias."""
