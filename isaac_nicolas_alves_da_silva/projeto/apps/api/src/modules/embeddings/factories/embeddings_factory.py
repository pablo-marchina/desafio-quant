"""Composicao das dependencias concretas do modulo embeddings."""

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.embeddings.application.ports import (
    ChunkSourceReader,
    EmbeddingTaskDispatcher,
)
from apps.api.src.modules.embeddings.application.public.embedding_job_submitter import (
    DefaultEmbeddingJobSubmitter,
    EmbeddingJobSubmitter,
)
from apps.api.src.modules.embeddings.application.public.embedding_service import (
    EmbeddingService,
)
from apps.api.src.modules.embeddings.application.public.vector_repository import (
    VectorRepository,
)
from apps.api.src.modules.embeddings.application.use_cases.create_embedding_job import (
    CreateEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.execute_embedding_job import (
    ExecuteEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.generate_chunk_embedding import (
    GenerateChunkEmbedding,
)
from apps.api.src.modules.embeddings.application.use_cases.get_embedding_job import (
    GetEmbeddingJob,
)
from apps.api.src.modules.embeddings.application.use_cases.upsert_chunk_embedding import (
    UpsertChunkEmbedding,
)
from apps.api.src.modules.embeddings.infrastructure.database.postgres_unit_of_work import (
    PostgresEmbeddingsUnitOfWork,
)
from apps.api.src.modules.embeddings.infrastructure.gemini.gemini_embedding_provider import (
    GeminiEmbeddingProvider,
)
from apps.api.src.modules.embeddings.infrastructure.ingestion_adapters.ingestion_chunk_reader import (
    IngestionChunkReader,
)
from apps.api.src.modules.embeddings.infrastructure.qdrant.qdrant_vector_repository import (
    QdrantVectorRepository,
)
from apps.api.src.modules.embeddings.infrastructure.queue.dramatiq_embedding_dispatcher import (
    DramatiqEmbeddingJobPublisher,
    DramatiqEmbeddingTaskDispatcher,
)
from apps.api.src.modules.ingestion.factories.ingestion_factory import IngestionFactory
from apps.api.src.shared.queue.dramatiq_broker import broker


class EmbeddingsFactory:
    """Ponto de composicao do modulo embeddings."""

    @staticmethod
    def create_embedding_service() -> EmbeddingService | None:
        """Cria o provider real de embeddings.

        Devolve ``None`` quando ``GEMINI_API_KEY`` nao esta configurada — sem
        fallback silencioso para o provider fake, que so existe para testes
        (``infrastructure/fake/deterministic_fake_provider.py``). A falta de
        servico e' tratada na hora do uso real, em
        ``GenerateChunkEmbedding.execute()``.
        """

        settings = get_settings()
        if not settings.gemini_api_key:
            return None

        return GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_embedding_model,
        )

    @staticmethod
    def create_generate_chunk_embedding() -> GenerateChunkEmbedding:
        """Cria o caso de uso pronto para gerar embeddings de chunks."""

        return GenerateChunkEmbedding(
            embedding_service=EmbeddingsFactory.create_embedding_service(),
        )

    @staticmethod
    def create_vector_repository() -> VectorRepository:
        """Cria o repositorio de vetores (Qdrant)."""

        settings = get_settings()
        return QdrantVectorRepository(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
        )

    @staticmethod
    def create_upsert_chunk_embedding() -> UpsertChunkEmbedding:
        """Cria o caso de uso pronto para gerar e persistir embeddings de chunks."""

        return UpsertChunkEmbedding(
            generate_chunk_embedding=EmbeddingsFactory.create_generate_chunk_embedding(),
            vector_repository=EmbeddingsFactory.create_vector_repository(),
        )

    @staticmethod
    def create_chunk_source_reader() -> ChunkSourceReader:
        """Cria o leitor de chunks, embrulhando o contrato publico do ingestion."""

        return IngestionChunkReader(
            IngestionFactory.create_ingested_document_reader()
        )

    @staticmethod
    def create_task_dispatcher() -> EmbeddingTaskDispatcher:
        return DramatiqEmbeddingTaskDispatcher(
            DramatiqEmbeddingJobPublisher(broker)
        )

    @staticmethod
    def create_create_embedding_job() -> CreateEmbeddingJob:
        return CreateEmbeddingJob(
            uow_factory=PostgresEmbeddingsUnitOfWork,
            task_dispatcher=EmbeddingsFactory.create_task_dispatcher(),
        )

    @staticmethod
    def create_execute_embedding_job() -> ExecuteEmbeddingJob:
        return ExecuteEmbeddingJob(
            uow_factory=PostgresEmbeddingsUnitOfWork,
            chunk_source_reader=EmbeddingsFactory.create_chunk_source_reader(),
            upsert_chunk_embedding=EmbeddingsFactory.create_upsert_chunk_embedding(),
            current_model_name=get_settings().gemini_embedding_model,
        )

    @staticmethod
    def create_get_embedding_job() -> GetEmbeddingJob:
        return GetEmbeddingJob(PostgresEmbeddingsUnitOfWork)

    @staticmethod
    def create_job_submitter() -> EmbeddingJobSubmitter:
        """Cria o contrato publico para submeter/acompanhar jobs (Orchestration V2)."""

        return DefaultEmbeddingJobSubmitter(
            create_embedding_job=EmbeddingsFactory.create_create_embedding_job(),
            get_embedding_job=EmbeddingsFactory.create_get_embedding_job(),
        )
