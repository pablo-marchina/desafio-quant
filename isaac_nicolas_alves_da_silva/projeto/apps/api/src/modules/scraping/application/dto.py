"""Objetos usados para transportar dados dentro da camada de aplicação.

DTO significa Data Transfer Object. Diferente das entidades do domínio, DTOs
não protegem regras de negócio ou possuem ciclo de vida. Eles apenas definem um
formato estável para a comunicação entre as partes do módulo.
"""

from dataclasses import dataclass, field

from uuid import UUID

from apps.api.src.modules.scraping.domain.enums import (
    AgentInvestigationDecision,
    ScrapingMethod,
    SemanticReviewDecision,
)
from apps.api.src.modules.scraping.domain.policies import ValidationSummary


@dataclass(frozen=True)
class ScrapingInput:
    """Dados que a aplicação entrega para qualquer estratégia de scraping."""

    # Começaremos recebendo somente uma URL. No futuro, este DTO pode ganhar
    # timeout, cabeçalhos permitidos ou contexto da startup.
    url: str


@dataclass(frozen=True)
class ScrapingOutput:
    """Resultado técnico padronizado produzido por qualquer scraper.

    BeautifulSoup, Playwright e Firecrawl deverão devolver o mesmo formato.
    Dessa forma, a pipeline não precisa conhecer detalhes dessas tecnologias.
    """

    # URL originalmente solicitada.
    source_url: str

    # URL final, importante para detectar e auditar redirecionamentos.
    final_url: str

    title: str | None
    raw_html: str
    raw_text: str

    status_code: int
    content_type: str
    method: ScrapingMethod

    # Metadados adicionais não essenciais ao contrato principal.
    metadata: dict[str, str | int | float | bool | None] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ValidationComponentResult:
    """Resultado padronizado produzido por um validador especializado.

    Validadores tecnico, textual e evidencial analisam aspectos diferentes,
    mas todos devolvem este mesmo formato para o validador composto combinar.
    """

    score: float
    problems: set[str] = field(default_factory=set)
    warnings: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class DeterministicValidationResult:
    """Medições objetivas produzidas pelos validadores.

    Os validadores técnicos e textuais preenchem este DTO. O método
    ``to_summary`` remove o detalhe de transporte e entrega ao domínio apenas
    os valores necessários para suas políticas.
    """

    technical_score: float
    text_score: float
    evidence_score: float
    quality_score: float = 0.0
    problems: set[str] = field(default_factory=set)
    warnings: set[str] = field(default_factory=set)

    def to_summary(self) -> ValidationSummary:
        """Converte o resultado da aplicação para o formato do domínio."""

        return ValidationSummary(
            technical_score=self.technical_score,
            text_score=self.text_score,
            evidence_score=self.evidence_score,
            quality_score=self.quality_score,
            problems=self.problems,
            warnings=self.warnings,
        )


@dataclass(frozen=True)
class SemanticValidationInput:
    """Contexto minimo entregue a uma implementacao de LLM."""

    url: str
    title: str | None
    raw_text: str
    deterministic: DeterministicValidationResult


@dataclass(frozen=True)
class SemanticAssessment:
    """Fatores estruturados produzidos pela LLM, sem confianca calculada."""

    startup_match_score: float
    evidence_clarity_score: float
    source_reliability_score: float
    statement_specificity_score: float
    context_completeness_score: float
    contradiction_detected: bool
    decision: SemanticReviewDecision
    reason: str


@dataclass(frozen=True)
class SemanticValidationResult:
    """Resultado final depois que o sistema calcula a confianca semantica."""

    assessment: SemanticAssessment
    semantic_confidence: float


@dataclass(frozen=True)
class InvestigationInput:
    """Contexto entregue ao agente quando a revisao simples nao basta.

    Reaproveita os DTOs ja existentes (``DeterministicValidationResult`` e
    ``SemanticValidationResult``) em vez de duplicar os mesmos campos. Assim,
    o agente recebe exatamente o que a pipeline ja calculou, sem precisar
    refazer nenhuma analise que ja foi feita nas etapas anteriores.
    """

    url: str
    title: str | None
    raw_text: str
    deterministic: DeterministicValidationResult
    semantic: SemanticValidationResult

    # Identificador da startup que esta sendo investigada. E opcional porque,
    # nesta primeira versao, a pipeline pode nao ter esse contexto disponivel
    # ainda. Quando presente, o agente pode usa-lo para validar identidade ou
    # consultar o RAG filtrando por essa startup.
    startup_id: UUID | None = None


@dataclass(frozen=True)
class InvestigationResult:
    """Resultado final produzido pelo agente, ja traduzido para o scraping.

    Quem monta este DTO e o adaptador
    (``infrastructure/agent_adapters/agents_semantic_investigator.py``), a
    partir da resposta do contrato publico do modulo ``agents``. A pipeline
    de scraping so conhece este formato.
    """

    decision: AgentInvestigationDecision
    reason: str
