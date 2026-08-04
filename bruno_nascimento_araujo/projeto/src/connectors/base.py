"""Contrato base dos conectores de extracao direta."""
from __future__ import annotations

import abc

from ..http_client import PoliteFetcher
from ..logging_conf import get_logger
from ..models import StartupRecord


class BaseConnector(abc.ABC):
    """Cada fonte implementa fetch() retornando StartupRecord normalizados.

    O orquestrador chama os conectores via asyncio.gather(return_exceptions=True),
    entao uma excecao aqui nao derruba os demais. Ainda assim, cada conector deve
    blindar o parsing por item para nao perder a fonte inteira por um registro ruim.
    """

    source_name: str = "base"

    def __init__(self, fetcher: PoliteFetcher) -> None:
        self.fetcher = fetcher
        self.log = get_logger(f"connector.{self.source_name}")

    @abc.abstractmethod
    async def fetch(self) -> list[StartupRecord]:
        ...

    async def run(self) -> list[StartupRecord]:
        """Wrapper com logging de inicio/fim e contagem."""
        self.log.info("Iniciando extracao (%s)...", self.source_name)
        records = await self.fetch()
        valid = [r for r in records if r.is_valid()]
        self.log.info("Concluido: %d registros validos de %s.", len(valid), self.source_name)
        return valid
