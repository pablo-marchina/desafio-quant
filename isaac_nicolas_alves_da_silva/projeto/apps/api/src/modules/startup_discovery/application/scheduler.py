"""Scheduler simples para discovery recorrente de startups.

O modulo nao depende de APScheduler/Celery beat: usa uma task asyncio do proprio
processo FastAPI. Isso e suficiente para ambiente local/MVP e fica desligado por
padrao. Em producao multi-worker, usar apenas um worker de scheduler ou trocar
por um scheduler externo com lock distribuido.
"""

import asyncio
from collections.abc import Callable
from typing import Protocol

from apps.api.src.shared.logging import get_logger

logger = get_logger(__name__)


class DiscoveryUseCase(Protocol):
    async def execute(self): ...


class StartupDiscoveryScheduler:
    """Executa `RunStartupDiscovery` em intervalo fixo."""

    def __init__(
        self,
        *,
        run_discovery_factory: Callable[[], DiscoveryUseCase],
        interval_seconds: float,
        run_on_startup: bool = False,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds deve ser maior que zero.")

        self._run_discovery_factory = run_discovery_factory
        self._interval_seconds = interval_seconds
        self._run_on_startup = run_on_startup
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._run_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Inicia a task recorrente no event loop atual."""

        if self.is_running:
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            self._run_loop(),
            name="startup-discovery-scheduler",
        )
        logger.info(
            "startup discovery scheduler started",
            extra={
                "interval_seconds": self._interval_seconds,
                "run_on_startup": self._run_on_startup,
            },
        )

    async def stop(self) -> None:
        """Para a task recorrente e cancela a espera atual."""

        if self._stop_event is not None:
            self._stop_event.set()

        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self._stop_event = None
            logger.info("startup discovery scheduler stopped")

    async def _run_loop(self) -> None:
        assert self._stop_event is not None

        if self._run_on_startup:
            await self._run_once()

        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval_seconds,
                )
            except TimeoutError:
                await self._run_once()

    async def _run_once(self) -> None:
        if self._run_lock.locked():
            logger.warning(
                "startup discovery run skipped because previous run is still active"
            )
            return

        async with self._run_lock:
            try:
                view = await self._run_discovery_factory().execute()
                logger.info(
                    "scheduled startup discovery run completed",
                    extra={
                        "run_id": str(view.id),
                        "status": view.status.value,
                        "jobs_submitted": view.jobs_submitted,
                    },
                )
            except Exception as error:
                logger.exception(
                    "scheduled startup discovery run failed",
                    extra={"reason": str(error)},
                )
