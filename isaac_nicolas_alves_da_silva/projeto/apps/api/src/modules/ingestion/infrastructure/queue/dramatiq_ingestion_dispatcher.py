"""Dispatcher que publica jobs de ingestion em uma fila Dramatiq."""

import asyncio
from uuid import UUID

from dramatiq import Message
from dramatiq.broker import Broker

from apps.api.src.modules.ingestion.application.ports import IngestionTaskDispatcher
from apps.api.src.modules.ingestion.domain.exceptions import IngestionTaskDispatchError


class DramatiqIngestionJobPublisher:
    """Publica mensagem compativel com o ingestion_worker.

    Usa `dramatiq.Message` diretamente para nao importar o actor do worker,
    evitando dependencia circular entre modulo e worker.
    """

    def __init__(
        self,
        broker: Broker,
        *,
        actor_name: str = "execute_ingestion_job",
        queue_name: str = "ingestion",
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


class DramatiqIngestionTaskDispatcher(IngestionTaskDispatcher):

    def __init__(self, publisher: DramatiqIngestionJobPublisher) -> None:
        self._publisher = publisher

    async def dispatch(self, *, job_id: UUID) -> None:
        try:
            await asyncio.to_thread(self._publisher.send, str(job_id))
        except Exception as exc:
            raise IngestionTaskDispatchError(
                "Nao foi possivel publicar o job na fila de ingestion."
            ) from exc
