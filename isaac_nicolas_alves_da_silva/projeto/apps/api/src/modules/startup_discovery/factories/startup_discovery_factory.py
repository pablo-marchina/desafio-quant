"""Composicao das dependencias concretas do modulo startup_discovery."""

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.orchestration.factories.orchestration_factory import (
    OrchestrationFactory,
)
from apps.api.src.modules.startup_discovery.application.scheduler import (
    StartupDiscoveryScheduler,
)
from apps.api.src.modules.startup_discovery.application.use_cases.get_discovery_run import (
    GetDiscoveryRun,
)
from apps.api.src.modules.startup_discovery.application.use_cases.run_discovery import (
    RunStartupDiscovery,
)
from apps.api.src.modules.startup_discovery.infrastructure.database.postgres_unit_of_work import (
    PostgresDiscoveryUnitOfWork,
)
from apps.api.src.modules.startup_discovery.infrastructure.enrichment.candidate_enrichment_service import (
    CandidateEnrichmentService,
)
from apps.api.src.modules.startup_discovery.infrastructure.hub_extractors.abstartups import (
    AbstartupsExtractor,
)
from apps.api.src.modules.startup_discovery.infrastructure.hub_extractors.inovativa import (
    InovativaBrasilExtractor,
)
from apps.api.src.modules.startup_discovery.infrastructure.hub_extractors.open_startups import (
    OpenStartupsExtractor,
)
from apps.api.src.modules.startup_discovery.infrastructure.orchestration_adapters.url_ingestion_adapter import (
    StartupDiscoveryUrlIngestionAdapter,
)
from apps.api.src.modules.startup_discovery.infrastructure.search_adapters.tavily_web_search_adapter import (
    TavilyWebSearchAdapter,
)
from apps.api.src.modules.startups.infrastructure.database.postgres_unit_of_work import (
    PostgresStartupsUnitOfWork,
)


def _url_extractors() -> dict:
    return {
        "inovativa": InovativaBrasilExtractor(),
        "abstartups": AbstartupsExtractor(),
    }


def _name_extractors() -> dict:
    return {
        "open_startups": OpenStartupsExtractor(),
    }


class StartupDiscoveryFactory:

    @staticmethod
    def create_run_discovery() -> RunStartupDiscovery:
        settings = get_settings()
        enricher = None
        if settings.tavily_api_key:
            search_adapter = TavilyWebSearchAdapter(
                api_key=settings.tavily_api_key,
                search_url=settings.tavily_search_url,
            )
            enricher = CandidateEnrichmentService(search_adapter)

        return RunStartupDiscovery(
            uow_factory=PostgresDiscoveryUnitOfWork,
            extractors=_url_extractors(),
            name_extractors=_name_extractors(),
            url_ingestion_submitter=StartupDiscoveryUrlIngestionAdapter(
                OrchestrationFactory.create_create_url_ingestion_job(),
                PostgresStartupsUnitOfWork,
            ),
            candidate_enricher=enricher,
            max_per_run=settings.startup_discovery_max_per_run,
        )

    @staticmethod
    def create_get_discovery_run() -> GetDiscoveryRun:
        return GetDiscoveryRun(PostgresDiscoveryUnitOfWork)

    @staticmethod
    def create_scheduler() -> StartupDiscoveryScheduler | None:
        settings = get_settings()
        if not settings.startup_discovery_scheduler_enabled:
            return None

        return StartupDiscoveryScheduler(
            run_discovery_factory=StartupDiscoveryFactory.create_run_discovery,
            interval_seconds=settings.startup_discovery_scheduler_interval_seconds,
            run_on_startup=settings.startup_discovery_scheduler_run_on_startup,
        )
