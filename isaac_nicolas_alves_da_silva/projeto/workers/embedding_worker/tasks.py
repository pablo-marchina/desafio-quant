"""Actors Dramatiq executados pelo worker de embeddings."""

from uuid import UUID

import dramatiq

from apps.api.src.modules.embeddings.domain.exceptions import (
    EmbeddingJobPartiallyFailedError,
)
from apps.api.src.modules.embeddings.factories.embeddings_factory import (
    EmbeddingsFactory,
)
from apps.api.src.shared.queue.dramatiq_broker import broker
from apps.api.src.shared.logging import get_logger, log_job

logger = get_logger(__name__)


@dramatiq.actor(
    broker=broker,
    queue_name="embeddings",
    max_retries=3,
)
async def execute_embedding_job(job_id: str) -> None:
    """Executa um job de embeddings recebido da fila.

    O worker transporta apenas o job_id. Toda a logica de leitura de
    chunks, geracao e persistencia de vetores fica no modulo de embeddings.
    Se ainda houver chunks pendentes apos esta tentativa, o caso de uso
    levanta uma excecao para o Dramatiq reentregar a mensagem.
    """

    with log_job(
        logger,
        "embedding job",
        expected_retry_exceptions=(EmbeddingJobPartiallyFailedError,),
        job_id=job_id,
    ):
        use_case = EmbeddingsFactory.create_execute_embedding_job()
        await use_case.execute(job_id=UUID(job_id))
