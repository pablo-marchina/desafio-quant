"""Portas que conectam a aplicacao de orchestration a outros modulos.

``orchestration`` mantem seu proprio vocabulario, decoupled das views
exatas de ``recommendations`` e ``briefing``. As implementacoes concretas
destas portas vivem em ``infrastructure/`` e sao o unico lugar que conhece
os contratos publicos dos dois modulos.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


class RecommendationsPort(ABC):
    """Contrato para disparar a geracao de recomendacoes de uma startup."""

    @abstractmethod
    async def generate(self, startup_id: UUID) -> int:
        """Gera as recomendacoes e retorna quantas foram criadas."""


class BriefingPort(ABC):
    """Contrato para disparar a geracao do briefing de uma startup."""

    @abstractmethod
    async def generate(self, startup_id: UUID) -> UUID:
        """Gera o briefing e retorna o id do briefing criado."""


@dataclass(frozen=True)
class StepStatus:
    """Vocabulario simplificado e proprio de orchestration para o status de
    um job downstream (scraping/ingestion/embeddings) — decoupled das views
    exatas de cada modulo, mesmo espirito de ``RecommendationsPort``/
    ``BriefingPort``."""

    is_done: bool
    is_failed: bool
    result_id: UUID | None
    error_message: str | None


class ScrapingPort(ABC):
    """Contrato para submeter e acompanhar um job de scraping (Orchestration V2)."""

    @abstractmethod
    async def submit(self, url: str, *, source_type: str = "startup_evidence") -> UUID:
        """Submete a URL e devolve o scraping_job_id."""

    @abstractmethod
    async def get_status(self, job_id: UUID) -> StepStatus:
        """Consulta o status; ``result_id`` e' o scraping_result_id quando concluido."""

    @abstractmethod
    async def get_html(self, result_id: UUID) -> str | None:
        """Retorna o HTML bruto do resultado aprovado, ou None se nao encontrado (P0d)."""


@dataclass(frozen=True)
class DocumentContentView:
    """Conteudo do documento ingerido, vocabulario proprio de orchestration."""

    title: str | None
    clean_text: str


@dataclass(frozen=True)
class StartupProfileSnapshot:
    """Recorte minimo do perfil usado pela orquestracao para decidir
    enriquecimento automatico, sem vazar DTOs internos de startups."""

    name: str
    website_url: str | None
    founders: list[str]
    funding_stage: str | None
    customers: list[str]
    evidence_urls: list[str]
    ai_workload_type: str = "unknown"
    deployment_stage: str = "unknown"
    gpu_need: str = "unknown"


@dataclass(frozen=True)
class StartupExtractionAttempt:
    """Status operacional da consolidacao estruturada no modulo startups."""

    succeeded: bool
    unavailable: bool = False
    timed_out: bool = False
    error_message: str | None = None


class IngestionPort(ABC):
    """Contrato para submeter e acompanhar um job de ingestion (Orchestration V2)."""

    @abstractmethod
    async def submit(
        self,
        scraping_result_id: UUID,
        *,
        source_type: str = "startup_evidence",
    ) -> UUID:
        """Submete o scraping_result_id e devolve o ingestion_job_id."""

    @abstractmethod
    async def get_status(self, job_id: UUID) -> StepStatus:
        """Consulta o status; ``result_id`` e' o document_id quando concluido."""

    @abstractmethod
    async def get_document_content(
        self, scraping_result_id: UUID
    ) -> DocumentContentView | None:
        """Le titulo e texto limpo do documento ingerido, ou ``None``."""


class EmbeddingsPort(ABC):
    """Contrato para submeter e acompanhar um job de embeddings (Orchestration V2)."""

    @abstractmethod
    async def submit(self, document_id: UUID) -> UUID:
        """Submete o document_id e devolve o embedding_job_id."""

    @abstractmethod
    async def get_status(self, job_id: UUID) -> StepStatus:
        """Consulta o status; ``result_id`` sempre None (ultimo passo)."""

    @abstractmethod
    async def delete_vectors_for_document(self, document_id: UUID) -> None:
        """Remove os vetores de um documento superado por um re-scrape.

        Best-effort do ponto de vista de quem chama: nao impede a
        conclusao do job se falhar, so deixa o vetor orfao pra uma limpeza
        futura.
        """


class UrlIngestionTaskDispatcher(ABC):
    """Porta para publicar/reenfileirar um url ingestion job na fila."""

    @abstractmethod
    async def dispatch(self, *, job_id: UUID) -> None:
        """Publica o job_id na fila de url ingestion."""


class StartupsPort(ABC):
    """Contrato para criar/enriquecer o perfil de uma startup a partir de
    conteudo ja ingerido (Orchestration V2). Vocabulario proprio de
    orchestration, decoupled dos DTOs internos de ``startups``."""

    @abstractmethod
    async def create_startup(self, *, name: str, website_url: str) -> UUID:
        """Cria a startup e devolve seu id."""

    @abstractmethod
    async def attach_evidence(
        self,
        *,
        startup_id: UUID,
        scraping_result_id: UUID,
        source_url: str,
        title: str | None,
        notes: str | None,
    ) -> None:
        """Associa o conteudo ingerido como evidencia da startup."""

    @abstractmethod
    async def try_extract(self, startup_id: UUID) -> StartupExtractionAttempt:
        """Aciona a extracao estruturada e retorna se ela completou."""

    @abstractmethod
    async def try_classify(self, startup_id: UUID) -> None:
        """Aciona a classificacao de maturidade de IA; nao-op se o servico nao estiver disponivel."""

    @abstractmethod
    async def get_profile(self, startup_id: UUID) -> StartupProfileSnapshot:
        """Le o perfil consolidado usado para decidir se faltam fontes."""


@dataclass(frozen=True)
class EnrichmentSearchCandidate:
    """URL candidata encontrada por busca externa."""

    url: str
    title: str | None = None
    snippet: str | None = None


class EnrichmentSearchPlannerPort(ABC):
    """Contrato da orquestracao para pedir queries de enriquecimento."""

    @abstractmethod
    async def plan_queries(
        self,
        *,
        startup_name: str,
        source_url: str,
        source_title: str | None,
        raw_text: str,
        missing_signals: list[str],
        known_terms: list[str],
        excluded_urls: list[str],
        max_queries: int = 3,
    ) -> list[str]:
        """Devolve queries priorizadas para buscar fontes melhores."""


class EnrichmentSearchExecutorPort(ABC):
    """Contrato da orquestracao para executar queries em busca web."""

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        excluded_urls: list[str],
        max_results: int = 2,
    ) -> list[EnrichmentSearchCandidate]:
        """Executa uma query e devolve URLs candidatas."""
