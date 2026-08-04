"""Entidades do dominio do modulo orchestration."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.api.src.modules.orchestration.domain.enums import (
    AnalysisJobStatus,
    UrlIngestionJobStatus,
)
from apps.api.src.modules.orchestration.domain.exceptions import (
    InvalidAnalysisJobTransitionError,
    InvalidUrlIngestionJobTransitionError,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class AnalysisJob:
    """Registro de uma execucao do pipeline recommendations -> briefing."""

    startup_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: AnalysisJobStatus = AnalysisJobStatus.PENDING
    recommendation_count: int | None = None
    briefing_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self) -> None:
        """Marca a execucao como iniciada."""

        if self.status is not AnalysisJobStatus.PENDING:
            raise InvalidAnalysisJobTransitionError(
                f"Somente analysis jobs pendentes podem iniciar. Estado atual: {self.status}."
            )

        self.status = AnalysisJobStatus.RUNNING
        self.started_at = utc_now()

    def complete(self, *, recommendation_count: int, briefing_id: UUID) -> None:
        """Conclui a execucao com o resultado agregado das etapas."""

        if self.status is not AnalysisJobStatus.RUNNING:
            raise InvalidAnalysisJobTransitionError(
                f"Somente analysis jobs em execucao podem concluir. Estado atual: {self.status}."
            )

        self.status = AnalysisJobStatus.COMPLETED
        self.recommendation_count = recommendation_count
        self.briefing_id = briefing_id
        self.finished_at = utc_now()

    def fail(self, reason: str) -> None:
        """Conclui a execucao com falha conhecida."""

        if self.status is not AnalysisJobStatus.RUNNING:
            raise InvalidAnalysisJobTransitionError(
                f"Somente analysis jobs em execucao podem falhar. Estado atual: {self.status}."
            )

        self.status = AnalysisJobStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()


@dataclass
class UrlIngestionJob:
    """Leva uma URL bruta atraves de scraping -> ingestion -> embeddings ->
    analise (startup/evidencia/extract/classify/recommendations/briefing).

    Maquina de estados (Orchestration V2): cada metodo so avanca um passo
    e guarda o ponteiro para o job downstream correspondente, para que
    ``AdvanceUrlIngestionJob`` saiba exatamente o que consultar na proxima
    chamada. Jobs com ``source_type != "startup_evidence"`` (ex:
    ``nvidia_knowledge``) pulam ``ANALYZING`` e concluem direto ao fim do
    embedding — nao faz sentido criar uma "startup" a partir de
    documentacao tecnica.
    """

    url: str
    source_type: str = "startup_evidence"
    id: UUID = field(default_factory=uuid4)
    status: UrlIngestionJobStatus = UrlIngestionJobStatus.PENDING
    scraping_job_id: UUID | None = None
    scraping_result_id: UUID | None = None
    ingestion_job_id: UUID | None = None
    document_id: UUID | None = None
    embedding_job_id: UUID | None = None
    startup_id: UUID | None = None
    parent_job_id: UUID | None = None
    enrichment_round: int = 0
    evidence_attached: bool = False
    recommendations_done: bool = False
    recommendation_count: int | None = None
    briefing_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start_scraping(self, scraping_job_id: UUID) -> None:
        if self.status is not UrlIngestionJobStatus.PENDING:
            raise InvalidUrlIngestionJobTransitionError(
                f"Somente jobs pendentes podem iniciar scraping. Estado atual: {self.status}."
            )
        self.status = UrlIngestionJobStatus.SCRAPING
        self.scraping_job_id = scraping_job_id
        self.started_at = utc_now()

    def start_ingesting(
        self, *, scraping_result_id: UUID, ingestion_job_id: UUID
    ) -> None:
        if self.status is not UrlIngestionJobStatus.SCRAPING:
            raise InvalidUrlIngestionJobTransitionError(
                f"Somente jobs em scraping podem iniciar ingestion. Estado atual: {self.status}."
            )
        self.status = UrlIngestionJobStatus.INGESTING
        self.scraping_result_id = scraping_result_id
        self.ingestion_job_id = ingestion_job_id

    def start_embedding(self, *, document_id: UUID, embedding_job_id: UUID) -> None:
        if self.status is not UrlIngestionJobStatus.INGESTING:
            raise InvalidUrlIngestionJobTransitionError(
                f"Somente jobs em ingestion podem iniciar embedding. Estado atual: {self.status}."
            )
        self.status = UrlIngestionJobStatus.EMBEDDING
        self.document_id = document_id
        self.embedding_job_id = embedding_job_id

    def start_analyzing(self) -> None:
        if self.status is not UrlIngestionJobStatus.EMBEDDING:
            raise InvalidUrlIngestionJobTransitionError(
                f"Somente jobs em embedding podem iniciar analise. Estado atual: {self.status}."
            )
        self.status = UrlIngestionJobStatus.ANALYZING

    def link_startup(self, startup_id: UUID) -> None:
        self.startup_id = startup_id

    def mark_evidence_attached(self) -> None:
        self.evidence_attached = True

    def record_recommendations(self, recommendation_count: int) -> None:
        """Persiste o resultado das recomendacoes antes do briefing.

        Chamado logo apos ``recommendations_port.generate()`` para que um
        crash ou falha do briefing nao force o retry a regerar recomendacoes
        — etapa cara quando o RAG/LLM esta envolvido.
        """
        self.recommendation_count = recommendation_count
        self.recommendations_done = True

    def record_analysis_result(
        self, *, recommendation_count: int, briefing_id: UUID
    ) -> None:
        self.recommendation_count = recommendation_count
        self.briefing_id = briefing_id

    def complete(self) -> None:
        if self.status not in (
            UrlIngestionJobStatus.EMBEDDING,
            UrlIngestionJobStatus.ANALYZING,
        ):
            raise InvalidUrlIngestionJobTransitionError(
                f"Somente jobs em embedding ou analise podem concluir. Estado atual: {self.status}."
            )
        self.status = UrlIngestionJobStatus.COMPLETED
        self.finished_at = utc_now()

    def fail(self, reason: str) -> None:
        if self.status in (
            UrlIngestionJobStatus.COMPLETED,
            UrlIngestionJobStatus.FAILED,
        ):
            raise InvalidUrlIngestionJobTransitionError(
                f"Job ja esta em estado terminal: {self.status}."
            )
        self.status = UrlIngestionJobStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()
