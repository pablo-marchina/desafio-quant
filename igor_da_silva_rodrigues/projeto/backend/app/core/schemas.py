from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AIClassification = Literal["AI-native", "AI-enabled", "API-consumer", "Non-AI"]
NVIDIATechnology = Literal[
    "NIM",
    "Triton",
    "TensorRT-LLM",
    "NeMo",
    "RAPIDS",
    "CUDA",
    "Riva",
    "Omniverse",
    "Clara",
    "Isaac",
    "Morpheus",
    "AI Enterprise",
    "Inception",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class PipelineInput(ContractModel):
    external_id: str | None = None
    startup_name: str = Field(min_length=1)
    site_oficial: str | None = None
    categoria: str | None = None
    descricao_curta: str | None = None
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = "Brasil"
    contexto: str | None = None
    dados_adicionais: dict[str, Any] = Field(default_factory=dict)

    @field_validator("site_oficial")
    @classmethod
    def validate_site(cls, value: str | None) -> str | None:
        if value is None:
            return None
        _ensure_absolute_url(value)
        return value


class SearchQuery(ContractModel):
    consulta: str = Field(min_length=1)
    objetivo: str = Field(min_length=1)
    camada: int = Field(ge=1, le=7)


class SearchTask(ContractModel):
    id: str = Field(min_length=1)
    tipo: Literal["busca_web", "busca_site", "acesso_direto", "feed_rss", "api_get"]
    consulta: str | None = None
    url: str | None = None
    extrator: str | None = None
    max_resultados: int | None = Field(default=None, ge=1, le=50)
    camada: int | None = Field(default=None, ge=1, le=7)
    objetivo: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value:
            _ensure_absolute_url(value)
        return value


class SearchPlanOutput(ContractModel):
    startup: str = Field(min_length=1)
    site_oficial: str | None = None
    hipotese_maturidade: str = Field(min_length=1)
    plano_consultas: list[SearchQuery]
    tarefas: list[SearchTask]
    fontes_prioritarias: list[dict[str, str]] = Field(default_factory=list)
    observacoes: str = ""

    @model_validator(mode="after")
    def validate_query_coverage(self) -> "SearchPlanOutput":
        if len(self.plano_consultas) < 18:
            raise ValueError("plano_consultas deve conter pelo menos 18 consultas")
        weighted = sum(item.camada in {3, 4} for item in self.plano_consultas)
        if weighted / len(self.plano_consultas) < 0.5:
            raise ValueError("as camadas 3 e 4 devem representar pelo menos 50% das consultas")
        return self


class SearchResult(ContractModel):
    titulo: str = Field(min_length=1)
    url: str
    snippet: str = Field(min_length=1)
    potencial_alto: bool = False
    provedor_busca: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _ensure_absolute_url(value)
        return value


class CollectedPage(ContractModel):
    url: str
    titulo_pagina: str | None = None
    conteudo_markdown: str | None = None
    conteudo_textual: str | None = None
    metadados: dict[str, Any] = Field(default_factory=dict)
    extrator: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _ensure_absolute_url(value)
        return value


class ScraperOutput(ContractModel):
    startup: str = Field(min_length=1)
    timestamp_coleta: str
    status: Literal["completo", "parcial", "falha"]
    metricas: dict[str, Any] = Field(default_factory=dict)
    resultados: list[dict[str, Any]] = Field(default_factory=list)
    resultados_buscas: list[SearchResult] = Field(default_factory=list)
    paginas_completas: list[CollectedPage] = Field(default_factory=list)
    varredura_complementar: list[dict[str, Any]] = Field(default_factory=list)
    erros: list[dict[str, Any]] = Field(default_factory=list)


class ValidatedEvidence(ContractModel):
    url: str
    dominio: str | None = None
    tipo_fonte: Literal["oficial", "imprensa", "ecossistema", "social", "outro"]
    credibilidade_fonte: float = Field(ge=0, le=1)
    trecho_evidencia: str = ""
    score_confianca: float = Field(ge=0, le=1)
    classificacao: Literal["alta", "media", "baixa"]
    mencao_forte: bool
    contem_evidencia_ia: bool
    declaracao_propria: bool
    tecnologias_detectadas: list[str] = Field(default_factory=list)
    corroborada: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _ensure_absolute_url(value)
        return value


class DiscardedEvidence(ContractModel):
    url: str
    motivo: str = Field(min_length=1)


class EvidenceSummary(ContractModel):
    tecnologias_detectadas: list[str] = Field(default_factory=list)
    fontes_corroboradas: int = Field(ge=0)
    afirmacoes_chave: list[str] = Field(default_factory=list)
    nota_geral_qualidade_evidencias: float = Field(ge=0, le=1)


class EvidenceValidationOutput(ContractModel):
    startup: str = Field(min_length=1)
    evidencias_validadas: list[ValidatedEvidence] = Field(default_factory=list)
    evidencias_medias: list[ValidatedEvidence] = Field(default_factory=list)
    evidencias_descartadas: list[DiscardedEvidence] = Field(default_factory=list)
    resumo_consolidado: EvidenceSummary
    erros_validacao: list[str] = Field(default_factory=list)


class EvidenceValidatorInput(ContractModel):
    site_oficial: str | None = None
    dados_brutos: ScraperOutput


class MaturityClassifierInput(ContractModel):
    validacao: EvidenceValidationOutput


class DetectedTechnologies(ContractModel):
    frameworks: list[str] = Field(default_factory=list)
    modelos_apis: list[str] = Field(default_factory=list)
    infraestrutura: list[str] = Field(default_factory=list)
    ferramentas_mlops: list[str] = Field(default_factory=list)


class AIMaturityOutput(ContractModel):
    startup: str = Field(min_length=1)
    classificacao: AIClassification
    nivel_maturidade: int = Field(ge=0, le=5)
    confianca_classificacao: float = Field(ge=0, le=1)
    justificativa: str = Field(min_length=1)
    tecnologias_utilizadas: DetectedTechnologies
    necessidades_limitacoes: list[str] = Field(default_factory=list)
    sugestao_inicial_stack_nvidia: str = ""
    evidencias_suporte: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_maturity_for_class(self) -> "AIMaturityOutput":
        if self.classificacao == "Non-AI" and self.nivel_maturidade != 0:
            raise ValueError("Non-AI deve ter nivel_maturidade 0")
        if self.classificacao != "Non-AI" and self.nivel_maturidade == 0:
            raise ValueError("classes com IA devem ter nivel_maturidade entre 1 e 5")
        return self


InceptionEligibility = Literal["eligible", "ineligible", "unknown"]
StartupStage = Literal["early", "growth", "scale", "unknown"]
InceptionNeed = Literal[
    "credits", "technical_support", "infrastructure", "go_to_market", "networking"
]


class InceptionFitInput(ContractModel):
    startup_profile: dict[str, Any]
    classificacao_ia: AIMaturityOutput
    validacao_evidencias: EvidenceValidationOutput | None = None


class InceptionNeedSignal(ContractModel):
    need: InceptionNeed
    status: Literal["identified", "not_identified", "unknown"]
    justification: str = Field(min_length=1)
    evidence_urls: list[str] = Field(default_factory=list)

    @field_validator("evidence_urls")
    @classmethod
    def validate_evidence_urls(cls, values: list[str]) -> list[str]:
        for value in values:
            _ensure_absolute_url(value)
        return values


class InceptionBenefitMatch(ContractModel):
    benefit: str = Field(min_length=1)
    match_status: Literal["strong", "possible", "unknown"]
    justification: str = Field(min_length=1)
    source_urls: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @field_validator("source_urls")
    @classmethod
    def validate_source_urls(cls, values: list[str]) -> list[str]:
        for value in values:
            _ensure_absolute_url(value)
        return values


class InceptionFitOutput(ContractModel):
    startup: str = Field(min_length=1)
    eligibility_status: InceptionEligibility
    eligibility_justification: str = Field(min_length=1)
    startup_stage: StartupStage
    stage_justification: str = Field(min_length=1)
    needs: list[InceptionNeedSignal] = Field(min_length=5, max_length=5)
    benefit_matches: list[InceptionBenefitMatch] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class KnowledgeMetadata(ContractModel):
    tecnologia: NVIDIATechnology
    tipo: Literal["documentacao", "whitepaper", "blog", "case_study", "github"]
    dores_relacionadas: list[
        Literal["custo", "latencia", "escalabilidade", "governanca", "privacidade", "vendor_lockin"]
    ] = Field(default_factory=list)
    perfil_aplicavel: list[Literal["AI-native", "AI-enabled", "API-consumer"]]
    titulo_secao: str = Field(min_length=1)
    url_fonte: str

    @field_validator("url_fonte")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _ensure_absolute_url(value)
        return value


class KnowledgeChunk(ContractModel):
    chunk_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: KnowledgeMetadata


class KnowledgeSourceInput(ContractModel):
    titulo: str = Field(min_length=1)
    url: str
    tecnologia: NVIDIATechnology
    tipo: Literal["documentacao", "whitepaper", "blog", "case_study", "github"]
    dores_relacionadas: list[
        Literal["custo", "latencia", "escalabilidade", "governanca", "privacidade", "vendor_lockin"]
    ] = Field(default_factory=list)
    perfil_aplicavel: list[Literal["AI-native", "AI-enabled", "API-consumer"]]

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _ensure_absolute_url(value)
        return value


class LoadedKnowledgeDocument(ContractModel):
    titulo: str
    content: str = Field(min_length=1)
    source: KnowledgeSourceInput


class IngestionReport(ContractModel):
    status: Literal["completo", "parcial", "falha"]
    fontes_processadas: int = Field(ge=0)
    fontes_com_erro: int = Field(ge=0)
    chunks_gerados: int = Field(ge=0)
    chunks_inseridos: int = Field(ge=0)
    collection_name: str
    errors: list[str] = Field(default_factory=list)


class RetrievedChunk(KnowledgeChunk):
    retrieval_score: float
    rerank_score: float | None = None


class RecommendationItem(ContractModel):
    tecnologia: NVIDIATechnology
    fit_score: float = Field(ge=0, le=1)
    justificativa: str = Field(min_length=1)
    dores_atendidas: list[str] = Field(default_factory=list)
    citacoes: list[str] = Field(min_length=1)


class NVIDIARecommendationOutput(ContractModel):
    startup: str = Field(min_length=1)
    recomendacoes: list[RecommendationItem] = Field(default_factory=list)
    chunks_utilizados: list[RetrievedChunk] = Field(default_factory=list, max_length=5)
    aviso: str | None = None


class RecommenderInput(ContractModel):
    classificacao_ia: AIMaturityOutput


RecommendationPhase = Literal["curto_prazo", "medio_prazo", "longo_prazo"]
ImplementationComplexity = Literal["baixa", "media", "alta"]


class RecommendationRefinerInput(ContractModel):
    classificacao_ia: AIMaturityOutput
    recomendacao_rag: NVIDIARecommendationOutput
    startup_profile: dict[str, Any] = Field(default_factory=dict)
    evidencias_altas: list[ValidatedEvidence] = Field(default_factory=list)


class PrioritizedTechnology(ContractModel):
    tecnologia: NVIDIATechnology
    ordem: int = Field(ge=1)
    fase: RecommendationPhase
    problema_resolvido: str = Field(min_length=1)
    beneficio: str = Field(min_length=1)
    dependencias: list[str] = Field(default_factory=list)
    riscos: str = Field(min_length=1)
    complexidade: ImplementationComplexity
    fontes_evidencia: list[str] = Field(default_factory=list)

    @field_validator("fontes_evidencia")
    @classmethod
    def validate_evidence_urls(cls, values: list[str]) -> list[str]:
        for value in values:
            _ensure_absolute_url(value)
        return values


class RoadmapPhase(ContractModel):
    tecnologias: list[NVIDIATechnology] = Field(default_factory=list)
    acoes: list[str] = Field(default_factory=list)


class RefinedRecommendation(ContractModel):
    tecnologias_priorizadas: list[PrioritizedTechnology] = Field(default_factory=list)
    roadmap: dict[RecommendationPhase, RoadmapPhase]
    fit_score: float = Field(ge=0, le=1)
    alertas: list[str] = Field(default_factory=list)
    perguntas_startup: list[str] = Field(default_factory=list)


class RecommendationRefinementOutput(ContractModel):
    startup: str = Field(min_length=1)
    recomendacao_refinada: RefinedRecommendation


class ImpactEstimatorInput(ContractModel):
    classificacao_ia: AIMaturityOutput
    recomendacao_refinada: RecommendationRefinementOutput
    dados_adicionais: dict[str, Any] = Field(default_factory=dict)


class TechnicalImpact(ContractModel):
    latencia: str = Field(min_length=1)
    custo: str = Field(min_length=1)
    vazao: str = Field(min_length=1)
    escalabilidade: str = Field(min_length=1)
    governanca_seguranca: str = Field(min_length=1)


class TechnologyImpactEstimate(ContractModel):
    tecnologia: NVIDIATechnology
    impacto_tecnico: TechnicalImpact
    impacto_negocio: str = Field(min_length=1)
    fontes_evidencia: list[str] = Field(default_factory=list)
    confianca: Literal["alta", "media", "baixa"]
    premissas: list[str] = Field(default_factory=list)

    @field_validator("fontes_evidencia")
    @classmethod
    def validate_impact_urls(cls, values: list[str]) -> list[str]:
        for value in values:
            _ensure_absolute_url(value)
        return values


class ImpactEstimationOutput(ContractModel):
    startup: str = Field(min_length=1)
    estimativas_impacto: list[TechnologyImpactEstimate] = Field(default_factory=list)
    indice_impacto_agregado: int = Field(ge=0, le=100)
    kpis_sugeridos: list[str] = Field(default_factory=list)
    incertezas: list[str] = Field(default_factory=list)
    resumo_executivo: str = Field(min_length=1)


class BriefingGeneratorInput(ContractModel):
    startup_profile: dict[str, Any]
    classificacao_ia: AIMaturityOutput
    recomendacao_refinada: RecommendationRefinementOutput
    estimativa_impacto: ImpactEstimationOutput
    validacao_evidencias: EvidenceValidationOutput | None = None
    inception_fit: InceptionFitOutput | None = None
    responsavel: str = "Time NVIDIA Inception Brasil"


class ExecutiveBriefingOutput(ContractModel):
    startup: str = Field(min_length=1)
    markdown: str = Field(min_length=1, max_length=12000)


class StageTrace(ContractModel):
    status: Literal["completo", "cache", "parcial", "falha"]
    duration_ms: float = Field(ge=0)
    attempts: int = Field(ge=0)
    tokens_consumidos: int = Field(ge=0, default=0)
    output: dict[str, Any] | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class PipelineOutput(ContractModel):
    startup: str
    status: Literal["completo", "parcial", "falha"]
    classificacao: AIClassification | None = None
    nivel_maturidade: int | None = Field(default=None, ge=0, le=5)
    inception_fit: InceptionFitOutput | None = None
    recomendacao: NVIDIARecommendationOutput | None = None
    recomendacao_refinada: RecommendationRefinementOutput | None = None
    impacto_estimado: ImpactEstimationOutput | None = None
    briefing_markdown: str | None = None
    pipeline_run_id: str | None = None
    trace: dict[str, StageTrace]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_errors: list[str] = Field(default_factory=list)
    critical_errors: list[str] = Field(default_factory=list)


def _ensure_absolute_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL deve ser absoluta e usar http ou https")
