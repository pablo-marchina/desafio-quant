"""Composicao das dependencias concretas do módulo de ingestion."""

from apps.api.src.modules.ingestion.application.ports import (
    IngestionTaskDispatcher,
    ScrapingResultReader,
)
from apps.api.src.modules.ingestion.application.public.ingested_reader import (
    IngestedDocumentReader,
)
from apps.api.src.modules.ingestion.application.public.ingestion_job_submitter import (
    DefaultIngestionJobSubmitter,
    IngestionJobSubmitter,
)
from apps.api.src.modules.ingestion.application.text_cleaner import TextCleaner
from apps.api.src.modules.ingestion.application.text_chunker import TextChunker
from apps.api.src.modules.ingestion.application.use_cases.create_ingestion_job import (
    CreateIngestionJob,
)
from apps.api.src.modules.ingestion.application.use_cases.execute_ingestion_job import (
    ExecuteIngestionJob,
)
from apps.api.src.modules.ingestion.application.use_cases.get_ingestion_job import (
    GetIngestionJob,
)
from apps.api.src.modules.ingestion.infrastructure.database.postgres_ingested_document_reader import (
    PostgresIngestedDocumentReader,
)
from apps.api.src.modules.ingestion.infrastructure.database.postgres_scraping_result_reader import (
    PostgresScrapingResultReader,
)
from apps.api.src.modules.ingestion.infrastructure.database.postgres_unit_of_work import (
    PostgresIngestionUnitOfWork,
)
from apps.api.src.modules.ingestion.infrastructure.queue.dramatiq_ingestion_dispatcher import (
    DramatiqIngestionJobPublisher,
    DramatiqIngestionTaskDispatcher,
)
from apps.api.src.shared.queue.dramatiq_broker import broker


class IngestionFactory:
    """Ponto de composicao do modulo de ingestion."""

    @staticmethod
    def create_text_cleaner() -> TextCleaner:
        return TextCleaner()

    @staticmethod
    def create_text_chunker() -> TextChunker:
        return TextChunker()

    @staticmethod
    def create_scraping_result_reader() -> ScrapingResultReader:
        return PostgresScrapingResultReader()

    @staticmethod
    def create_task_dispatcher() -> IngestionTaskDispatcher:
        return DramatiqIngestionTaskDispatcher(
            DramatiqIngestionJobPublisher(broker)
        )

    @staticmethod
    def create_execute_ingestion_job() -> ExecuteIngestionJob:
        return ExecuteIngestionJob(
            uow_factory=PostgresIngestionUnitOfWork,
            scraping_result_reader=IngestionFactory.create_scraping_result_reader(),
            text_cleaner=IngestionFactory.create_text_cleaner(),
            text_chunker=IngestionFactory.create_text_chunker(),
        )

    @staticmethod
    def create_create_ingestion_job() -> CreateIngestionJob:
        return CreateIngestionJob(
            uow_factory=PostgresIngestionUnitOfWork,
            task_dispatcher=IngestionFactory.create_task_dispatcher(),
        )

    @staticmethod
    def create_get_ingestion_job() -> GetIngestionJob:
        return GetIngestionJob(PostgresIngestionUnitOfWork)

    @staticmethod
    def create_ingested_document_reader() -> IngestedDocumentReader:
        return PostgresIngestedDocumentReader()

    @staticmethod
    def create_job_submitter() -> IngestionJobSubmitter:
        """Cria o contrato publico para submeter/acompanhar jobs (Orchestration V2)."""

        return DefaultIngestionJobSubmitter(
            create_ingestion_job=IngestionFactory.create_create_ingestion_job(),
            get_ingestion_job=IngestionFactory.create_get_ingestion_job(),
        )
