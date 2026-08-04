from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.models import Evidence, Recommendation, ScrapeRun, Startup


class StructuredRepository(Protocol):
    def save_startup(self, startup: Startup) -> Startup:
        ...

    def save_evidences(self, evidences: list[Evidence]) -> list[Evidence]:
        ...

    def save_scrape_run(self, scrape_run: ScrapeRun) -> ScrapeRun:
        ...

    def save_recommendations(
        self, recommendations: list[Recommendation]
    ) -> list[Recommendation]:
        ...


@dataclass
class InMemoryStructuredRepository:
    startups: dict[str, Startup] | None = None
    evidences: list[Evidence] | None = None
    scrape_runs: list[ScrapeRun] | None = None
    recommendations: list[Recommendation] | None = None

    def __post_init__(self) -> None:
        if self.startups is None:
            self.startups = {}
        if self.evidences is None:
            self.evidences = []
        if self.scrape_runs is None:
            self.scrape_runs = []
        if self.recommendations is None:
            self.recommendations = []

    def save_startup(self, startup: Startup) -> Startup:
        self.startups[startup.name] = startup
        return startup

    def save_evidences(self, evidences: list[Evidence]) -> list[Evidence]:
        self.evidences.extend(evidences)
        return evidences

    def save_scrape_run(self, scrape_run: ScrapeRun) -> ScrapeRun:
        self.scrape_runs.append(scrape_run)
        return scrape_run

    def save_recommendations(
        self, recommendations: list[Recommendation]
    ) -> list[Recommendation]:
        self.recommendations.extend(recommendations)
        return recommendations


class PostgresStructuredRepository:
    """
    Ponto de integracao para Supabase/Postgres.
    TODO: implementar upsert/relacionamentos reais via SQLAlchemy Session
    quando as credenciais e a estrategia de migrations estiverem definidas.
    """

    def __init__(self) -> None:
        self._message = (
            "Persistencia real em Supabase/Postgres ainda nao implementada. "
            "Use InMemoryStructuredRepository ou adicione a Session SQLAlchemy."
        )

    def save_startup(self, startup: Startup) -> Startup:
        raise NotImplementedError(self._message)

    def save_evidences(self, evidences: list[Evidence]) -> list[Evidence]:
        raise NotImplementedError(self._message)

    def save_scrape_run(self, scrape_run: ScrapeRun) -> ScrapeRun:
        raise NotImplementedError(self._message)

    def save_recommendations(
        self, recommendations: list[Recommendation]
    ) -> list[Recommendation]:
        raise NotImplementedError(self._message)
