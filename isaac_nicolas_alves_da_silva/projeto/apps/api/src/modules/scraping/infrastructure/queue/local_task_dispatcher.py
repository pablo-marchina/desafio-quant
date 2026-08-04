"""Dispatcher temporário que executa tarefas no mesmo processo."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from apps.api.src.modules.scraping.application.ports import TaskDispatcher


# Este alias torna explícito o contrato da função que executará um job:
# recebe um UUID e não retorna resultado de negócio.
JobExecutor = Callable[[UUID], Awaitable[None]]


class LocalTaskDispatcher(TaskDispatcher):
    """Encaminha o job para uma função assíncrona no processo atual.

    Esta implementação é adequada para desenvolvimento e aprendizado, mas não
    oferece isolamento, retries ou persistência de fila. Em produção, será
    substituída por um adaptador Dramatiq/Redis.
    """

    def __init__(self, job_executor: JobExecutor) -> None:
        self.job_executor = job_executor

    async def dispatch(self, job_id: UUID) -> None:
        """Executa imediatamente a função configurada com o ID do job."""

        await self.job_executor(job_id)
