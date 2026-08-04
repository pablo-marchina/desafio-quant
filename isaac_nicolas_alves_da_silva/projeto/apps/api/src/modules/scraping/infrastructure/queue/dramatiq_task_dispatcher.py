"""Dispatcher que publica jobs de scraping em uma fila Dramatiq."""

import asyncio
from typing import Protocol
from uuid import UUID

from dramatiq import Message
from dramatiq.broker import Broker

from apps.api.src.modules.scraping.application.ports import TaskDispatcher
from apps.api.src.modules.scraping.domain.exceptions import TaskDispatchError


class JobActor(Protocol):
    """Parte minima de um publicador necessaria para enviar uma task."""

    def send(self, job_id: str) -> object:
        """Publica uma mensagem contendo o identificador serializavel."""


class DramatiqJobPublisher:
    """Publica a mensagem do actor sem importar o processo worker."""

    def __init__(
        self,
        broker: Broker,
        *,
        actor_name: str = "execute_scraping_job",
        queue_name: str = "scraping",
    ) -> None:
        self.broker = broker
        self.actor_name = actor_name
        self.queue_name = queue_name

    def send(self, job_id: str) -> object:
        """Cria e envia uma mensagem compativel com o actor do worker."""

        message = Message(
            queue_name=self.queue_name,
            actor_name=self.actor_name,
            args=(job_id,),
            kwargs={},
            options={},
        )

        return self.broker.enqueue(message)


class DramatiqTaskDispatcher(TaskDispatcher):
    """Envia identificadores de jobs para um actor Dramatiq."""

    def __init__(self, actor: JobActor) -> None:
        # Receber o actor por injecao evita importar o worker externo dentro do
        # modulo e facilita testar o dispatcher sem conectar ao Redis.
        self.actor = actor

    async def dispatch(self, job_id: UUID) -> None:
        """Publica o UUID como string sem bloquear o event loop da API."""

        # Actor.send usa o cliente Redis sincrono. Executa-lo em outra thread
        # evita bloquear outras requisicoes async enquanto a mensagem e enviada.
        try:
            await asyncio.to_thread(self.actor.send, str(job_id))
        except Exception as error:
            raise TaskDispatchError(
                "Nao foi possivel publicar o job na fila de scraping."
            ) from error
