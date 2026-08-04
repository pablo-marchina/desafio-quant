"""Contratos (ports) que a aplicacao define e a infraestrutura implementa."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from apps.api.src.modules.startup_discovery.application.dto import (
    DiscoveredCandidateItem,
    StartupCandidate,
)


class HubLinkExtractor(ABC):
    """Extrai candidatos de startups (modo URL) de um hub."""

    @abstractmethod
    async def extract(
        self,
        listing_url: str,
        *,
        limit: int,
    ) -> Sequence[StartupCandidate | str]: ...


class HubNameExtractor(ABC):
    """Extrai nomes de startups de um hub que nao fornece URLs diretas."""

    @abstractmethod
    async def extract(
        self,
        listing_url: str,
        *,
        limit: int,
    ) -> list[DiscoveredCandidateItem]: ...


@dataclass(frozen=True)
class WebSearchResult:
    url: str
    title: str
    snippet: str


class WebSearchPort(ABC):
    """Executa busca web e retorna resultados com URL, titulo e trecho."""

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]: ...


class StartupUrlIngestionSubmitter(ABC):
    """Submete uma URL de startup ao pipeline de url_ingestion_jobs."""

    @abstractmethod
    async def submit(self, url: str) -> object: ...
