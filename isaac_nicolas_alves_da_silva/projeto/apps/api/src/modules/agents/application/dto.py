"""DTOs publicos do modulo agents.

Estes DTOs sao o "idioma" que outros modulos usam para falar com ``agents``.
Eles usam apenas tipos primitivos e estruturas simples (dict, list, str,
float) de proposito: assim, ``agents`` nunca precisa importar DTOs de
``scraping`` (ou de qualquer outro modulo), e ``scraping`` nunca precisa
importar enums internos de ``agents``.

Quem traduz entre os DTOs internos de ``scraping``
(``InvestigationInput``/``InvestigationResult``, em
``scraping/application/dto.py``) e estes DTOs publicos e o adaptador:
``scraping/infrastructure/agent_adapters/agents_semantic_investigator.py``.
"""

from dataclasses import dataclass, field
from uuid import UUID

from apps.api.src.modules.agents.domain.enums import (
    AgentDecision,
    AgentRunStatus,
    AgentType,
    ExtractedFundingStage,
    StartupMaturityLevel,
)


@dataclass(frozen=True)
class EvidenceValidationInput:
    """Contexto entregue ao Evidence Validation Agent.

    Contem o que a pipeline de scraping ja apurou: o conteudo coletado, os
    scores deterministicos e o resultado da revisao semantica simples (v7)
    que indicou a necessidade de investigacao.
    """

    url: str
    title: str | None
    raw_text: str

    # Scores deterministicos (0 a 1), calculados antes da revisao semantica.
    technical_score: float
    text_score: float
    evidence_score: float
    quality_score: float
    deterministic_problems: list[str] = field(default_factory=list)
    deterministic_warnings: list[str] = field(default_factory=list)

    # Fatores e decisao produzidos pela revisao semantica simples (v7), que
    # motivaram o acionamento do agente.
    startup_match_score: float = 0.0
    evidence_clarity_score: float = 0.0
    source_reliability_score: float = 0.0
    statement_specificity_score: float = 0.0
    context_completeness_score: float = 0.0
    contradiction_detected: bool = False
    semantic_decision: str = ""
    semantic_reason: str = ""
    semantic_confidence: float = 0.0

    # Identificador da startup investigada, quando disponivel.
    startup_id: UUID | None = None


@dataclass(frozen=True)
class EvidenceValidationResult:
    """Resultado final produzido pelo Evidence Validation Agent."""

    decision: AgentDecision
    reason: str


@dataclass(frozen=True)
class SearchPlanInput:
    """Contexto entregue ao Search Planner Agent.

    Este DTO nasce quando uma evidencia nao e suficiente e o sistema precisa
    planejar novas buscas. Ele nao cria jobs e nao chama scraper: ele apenas
    descreve o problema para o agente gerar queries.
    """

    startup_name: str | None
    source_url: str
    source_title: str | None
    raw_text: str
    reason: str
    known_terms: list[str] = field(default_factory=list)
    excluded_urls: list[str] = field(default_factory=list)
    max_queries: int = 5


@dataclass(frozen=True)
class SearchQuerySuggestion:
    """Uma query sugerida pelo Search Planner Agent."""

    query: str
    purpose: str
    priority: int


@dataclass(frozen=True)
class SearchPlanResult:
    """Plano de busca gerado pelo Search Planner Agent."""

    queries: list[SearchQuerySuggestion]
    reason: str


@dataclass(frozen=True)
class SearchResultCandidate:
    """Resultado candidato devolvido por um executor de busca web."""

    url: str
    title: str | None = None
    snippet: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class SearchExecutionResult:
    """Resultados de uma query ja executada em um provedor de busca."""

    query: str
    results: list[SearchResultCandidate]


@dataclass(frozen=True)
class StartupClassificationInput:
    """Contexto entregue ao Startup Classifier Agent.

    Reune o perfil e as evidencias da startup, ja traduzidos pelo
    adaptador de ``startups`` para o vocabulario de ``agents``.
    """

    name: str
    sector: str | None
    description: str | None
    country: str | None
    website_url: str | None
    evidence_texts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StartupClassificationResult:
    """Resultado final produzido pelo Startup Classifier Agent."""

    level: StartupMaturityLevel
    reason: str


@dataclass(frozen=True)
class ExtractionInput:
    """Contexto entregue ao Extraction Agent.

    Reune o perfil e as evidencias da startup, ja traduzidos pelo
    adaptador de ``startups`` para o vocabulario de ``agents``.
    """

    name: str
    sector: str | None
    description: str | None
    evidence_texts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractionResult:
    """Dados estruturados extraidos pelo Extraction Agent.

    Campos sao "melhor esforco": quando a evidencia nao menciona o dado,
    o agente deve devolver lista vazia/``UNKNOWN``/``None``, nunca
    inferir ou inventar.

    Os campos de perfil de IA (ai_workload_type etc.) usam strings simples
    ("unknown" como padrao) em vez dos enums de ``startups`` — isso mantem o
    boundary correto. O adaptador em
    ``startups/infrastructure/agent_adapters/`` faz a traducao para os enums.
    """

    founders: list[str]
    funding_stage: ExtractedFundingStage
    funding_amount_usd: float | None
    customers: list[str]
    sector: str | None = None
    description: str | None = None
    country: str | None = None
    # Perfil estruturado de IA (Briefing V4, passo 2)
    ai_workload_type: str = "unknown"
    model_type: str = "unknown"
    data_modality: str = "unknown"
    deployment_stage: str = "unknown"
    infra_environment: str = "unknown"
    gpu_need: str = "unknown"
    latency_requirement: str = "unknown"
    scale_signal: str | None = None
    current_tools: list[str] = field(default_factory=list)
    business_goal: str | None = None
    field_confidence: dict[str, float] = field(default_factory=dict)
    field_evidence_ids: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class NvidiaRagInput:
    """Contexto entregue ao NVIDIA RAG Agent.

    O agente consulta apenas a base de conhecimento NVIDIA (``rag`` filtrado
    por ``source_type="nvidia_knowledge"``) — isso e' decisao interna do
    adaptador que chama ``rag``, nao um parametro deste DTO.
    """

    query: str
    limit: int = 5


@dataclass(frozen=True)
class NvidiaRagCitation:
    """Uma citacao usada para fundamentar a resposta do NVIDIA RAG Agent."""

    source_url: str
    quote: str


@dataclass(frozen=True)
class NvidiaRagResult:
    """Resposta final produzida pelo NVIDIA RAG Agent, com citacoes."""

    answer: str
    citations: list[NvidiaRagCitation]


@dataclass(frozen=True)
class RecommendationAgentInput:
    """Contexto entregue ao Recommendation Agent."""

    startup_id: UUID


@dataclass(frozen=True)
class RecommendationCandidate:
    """Uma recomendacao candidata, no vocabulario interno de ``agents``.

    Reflete o resultado deterministico de ``recommendations`` (a fonte de
    verdade para score/matched_keywords) mais a justificativa, que pode ser
    substituida pela versao em linguagem de negocio apos a revisao do
    agente. Candidatos ambiguos podem ser descartados pela revisao; os
    confiantes sao sempre mantidos (decisao aplicada em codigo, nao confiada
    so ao prompt).
    """

    technology_slug: str
    technology_name: str
    category: str
    score: float
    justification: str
    matched_keywords: list[str]


@dataclass(frozen=True)
class RecommendationAgentResult:
    """Resultado final produzido pelo Recommendation Agent."""

    recommendations: list[RecommendationCandidate]


@dataclass(frozen=True)
class BriefingAgentInput:
    """Contexto entregue ao Briefing Agent."""

    startup_id: UUID


@dataclass(frozen=True)
class BriefingAgentResult:
    """Resultado final produzido pelo Briefing Agent.

    ``content`` e' a versao final em Markdown — reescrita em linguagem
    executiva quando a revisao preserva as citacoes do template
    deterministico, ou o conteudo deterministico original sem alteracao
    quando a reescrita perde alguma citacao (fallback seguro aplicado em
    codigo, nao confiado so ao prompt).
    """

    content: str
    briefing_id: UUID


@dataclass(frozen=True)
class CreateAgentRunInput:
    """Entrada para criar uma execucao assincrona de agente."""

    agent_type: AgentType
    input_payload: dict[str, object]


@dataclass(frozen=True)
class AgentRunView:
    """DTO de leitura de uma execucao de agente."""

    id: UUID
    agent_type: AgentType
    status: AgentRunStatus
    input_payload: dict[str, object]
    output_payload: dict[str, object] | None
    error_message: str | None
