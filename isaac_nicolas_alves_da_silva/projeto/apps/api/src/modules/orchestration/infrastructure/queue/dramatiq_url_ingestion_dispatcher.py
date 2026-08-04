"""Dispatcher que publica url ingestion jobs em uma fila Dramatiq."""

import asyncio
from uuid import UUID

from dramatiq import Message
from dramatiq.broker import Broker

from apps.api.src.modules.orchestration.application.ports import (
    UrlIngestionTaskDispatcher,
)
from apps.api.src.modules.orchestration.domain.exceptions import (
    UrlIngestionTaskDispatchError,
)


class DramatiqUrlIngestionJobPublisher:
    """Publica mensagem compativel com o orchestration_worker.

    Usa `dramatiq.Message` diretamente para nao importar o actor do worker,
    evitando dependencia circular entre modulo e worker (mesmo padrao de
    `DramatiqEmbeddingJobPublisher`).
    """

    def __init__(
        self,
        broker: Broker,
        *,
        actor_name: str = "advance_url_ingestion_job",
        queue_name: str = "url_ingestion",
    ) -> None:
        self._broker = broker
        self._actor_name = actor_name
        self._queue_name = queue_name

    def send(self, job_id: str) -> object:
        message = Message(
            queue_name=self._queue_name,
            actor_name=self._actor_name,
            args=(job_id,),
            kwargs={},
            options={},
        )
        return self._broker.enqueue(message)


class DramatiqUrlIngestionTaskDispatcher(UrlIngestionTaskDispatcher):

    def __init__(self, publisher: DramatiqUrlIngestionJobPublisher) -> None:
        self._publisher = publisher

    async def dispatch(self, *, job_id: UUID) -> None:
        try:
            await asyncio.to_thread(self._publisher.send, str(job_id))
        except Exception as exc:
            raise UrlIngestionTaskDispatchError(
                "Nao foi possivel publicar o job na fila de url ingestion."
            ) from exc
