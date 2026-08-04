"""Actors Dramatiq executados pelo worker de orchestration."""

from uuid import UUID

import dramatiq

from apps.api.src.modules.orchestration.domain.exceptions import (
    UrlIngestionStillProcessingError,
)
from apps.api.src.modules.orchestration.factories.orchestration_factory import (
    OrchestrationFactory,
)
from apps.api.src.shared.queue.dramatiq_broker import broker
from apps.api.src.shared.logging import get_logger, log_job

logger = get_logger(__name__)


@dramatiq.actor(
    broker=broker,
    queue_name="url_ingestion",
    max_retries=50,
    min_backoff=5_000,
    max_backoff=300_000,
)
async def advance_url_ingestion_job(job_id: str) -> None:
    """Avanca um passo do url ingestion job recebido da fila.

    O worker transporta apenas o job_id. ``AdvanceUrlIngestionJob`` decide
    qual etapa downstream (scraping/ingestion/embeddings) checar ou
    submeter. Enquanto o job nao chega a um estado terminal, o caso de uso
    levanta ``UrlIngestionStillProcessingError`` e o Dramatiq reentrega a
    mesma mensagem com backoff -- a fila e' o proprio loop de polling, sem
    scheduler customizado. ``max_retries=50`` com backoff entre 5s e 5min
    da' ate' ~4h de tentativas automaticas antes do job ficar parado num
    estado intermediario (mesma categoria de limite conhecido aceito na
    Embeddings V4).
    """

    with log_job(
        logger,
        "url ingestion job advance",
        expected_retry_exceptions=(UrlIngestionStillProcessingError,),
        job_id=job_id,
    ):
        use_case = OrchestrationFactory.create_advance_url_ingestion_job()
        await use_case.execute(job_id=UUID(job_id))
