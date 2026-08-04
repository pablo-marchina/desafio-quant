"""Composicao das dependencias concretas do modulo de scraping."""

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.agents.factories.agents_factory import AgentsFactory
from apps.api.src.modules.scraping.application.quality_scoring_service import (
    QualityScoringService,
)
from apps.api.src.modules.scraping.application.scraping_limits import (
    PipelineLimits,
    ScrapingLimits,
)
from apps.api.src.modules.scraping.application.scraping_pipeline import (
    ScrapingPipeline,
)
from apps.api.src.modules.scraping.application.strategy_selector import (
    ScrapingStrategySelector,
)
from apps.api.src.modules.scraping.application.use_cases.create_scraping_job import (
    CreateScrapingJob,
)
from apps.api.src.modules.scraping.application.use_cases.execute_scraping_job import (
    ExecuteScrapingJob,
)
from apps.api.src.modules.scraping.application.use_cases.get_scraping_job import (
    GetScrapingJob,
)
from apps.api.src.modules.scraping.application.use_cases.get_scraping_result import (
    GetScrapingResult,
)
from apps.api.src.modules.scraping.application.public.result_reader import (
    DefaultScrapingResultHtmlReader,
    ScrapingResultHtmlReader,
)
from apps.api.src.modules.scraping.application.public.job_submitter import (
    DefaultScrapingJobSubmitter,
    ScrapingJobSubmitter,
)
from apps.api.src.modules.scraping.domain.policies import (
    ContentAcceptancePolicy,
    FallbackPolicy,
    ValidationDecisionPolicy,
)
from apps.api.src.modules.scraping.domain.repositories import ScrapingAttemptRepository
from apps.api.src.modules.scraping.infrastructure.database.postgres_unit_of_work import (
    PostgresScrapingUnitOfWork,
)
from apps.api.src.shared.queue.dramatiq_broker import broker
from apps.api.src.modules.scraping.infrastructure.queue.dramatiq_task_dispatcher import (
    DramatiqJobPublisher,
    DramatiqTaskDispatcher,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.beautifulsoup_scraper import (
    BeautifulSoupScraper,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.playwright_scraper import (
    PlaywrightScraper,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.trafilatura_scraper import (
    TrafilaturaScraper,
)
from apps.api.src.modules.scraping.infrastructure.scrapers.firecrawl_scraper import (
    FirecrawlScraper,
)
from apps.api.src.modules.scraping.infrastructure.agent_adapters.agents_semantic_investigator import (
    AgentsSemanticInvestigator,
)
from apps.api.src.modules.scraping.infrastructure.security.url_guard import UrlGuard
from apps.api.src.modules.scraping.infrastructure.semantic_validators.gemini_semantic_validator import (
    GeminiSemanticValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.composite_deterministic_validator import (
    CompositeDeterministicValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.evidence_validator import (
    EvidenceValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.technical_validator import (
    TechnicalValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.textual_validator import (
    TextualValidator,
)


class ScrapingFactory:
    """Cria casos de uso com todas as dependencias concretas necessarias.

    Este e o ponto de composicao: ele conhece PostgreSQL, BeautifulSoup e o
    dispatcher Dramatiq, enquanto os casos de uso continuam dependendo apenas de
    contratos definidos pelas camadas internas.
    """

    @staticmethod
    def create_unit_of_work() -> PostgresScrapingUnitOfWork:
        """Cria uma nova sessao/transacao PostgreSQL para cada operacao."""

        return PostgresScrapingUnitOfWork()

    @staticmethod
    def create_pipeline(
        attempt_repository: ScrapingAttemptRepository,
    ) -> ScrapingPipeline:
        """Monta a pipeline usando o repositorio da transacao atual."""

        settings = get_settings()
        beautifulsoup_scraper = BeautifulSoupScraper(
            url_guard=UrlGuard(),
            limits=ScrapingLimits(),
        )
        playwright_scraper = PlaywrightScraper(
            url_guard=UrlGuard(),
            # Renderizar JavaScript normalmente exige mais tempo que baixar
            # HTML estatico, por isso esta estrategia recebe timeout maior.
            limits=ScrapingLimits(timeout_seconds=30),
        )
        trafilatura_scraper = TrafilaturaScraper(
            source_scraper=beautifulsoup_scraper,
        )
        firecrawl_scraper = (
            FirecrawlScraper(api_key=settings.firecrawl_api_key)
            if settings.firecrawl_api_key
            else None
        )
        semantic_validator = (
            GeminiSemanticValidator(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
            )
            if settings.gemini_api_key
            else None
        )

        # v8: o investigador so existe se o modulo agents conseguir montar o
        # seu servico publico (hoje, depende da mesma chave do Gemini). Se
        # nao existir, a pipeline se comporta como na v7.
        evidence_validation_service = (
            AgentsFactory.create_evidence_validation_service()
        )
        semantic_investigator = (
            AgentsSemanticInvestigator(evidence_validation_service)
            if evidence_validation_service is not None
            else None
        )

        strategies = [
            beautifulsoup_scraper,
            trafilatura_scraper,
            playwright_scraper,
        ]
        if firecrawl_scraper is not None:
            strategies.append(firecrawl_scraper)

        return ScrapingPipeline(
            strategy_selector=ScrapingStrategySelector(strategies),
            validator=CompositeDeterministicValidator(
                technical_validator=TechnicalValidator(),
                textual_validator=TextualValidator(),
                evidence_validator=EvidenceValidator(),
            ),
            scoring_service=QualityScoringService(),
            decision_policy=ValidationDecisionPolicy(
                ContentAcceptancePolicy(),
                FallbackPolicy(),
            ),
            attempt_repository=attempt_repository,
            limits=PipelineLimits(
                total_timeout_seconds=get_settings().scraping_startup_timeout_seconds,
                reference_total_timeout_seconds=get_settings().scraping_reference_timeout_seconds,
            ),
            semantic_validator=semantic_validator,
            semantic_investigator=semantic_investigator,
        )

    @classmethod
    def create_execute_scraping_job(cls) -> ExecuteScrapingJob:
        """Cria o caso de uso executado pelo dispatcher ou futuro worker."""

        return ExecuteScrapingJob(
            unit_of_work_factory=cls.create_unit_of_work,
            pipeline_factory=cls.create_pipeline,
        )

    @classmethod
    def create_create_scraping_job(cls) -> CreateScrapingJob:
        """Cria o caso de uso que persiste e despacha novos jobs."""

        return CreateScrapingJob(
            unit_of_work_factory=cls.create_unit_of_work,
            task_dispatcher=DramatiqTaskDispatcher(
                DramatiqJobPublisher(broker),
            ),
        )

    @classmethod
    def create_get_scraping_job(cls) -> GetScrapingJob:
        """Cria o caso de uso de consulta de job e tentativas."""

        return GetScrapingJob(unit_of_work_factory=cls.create_unit_of_work)

    @classmethod
    def create_get_scraping_result(cls) -> GetScrapingResult:
        """Cria o caso de uso de consulta do conteudo aprovado."""

        return GetScrapingResult(unit_of_work_factory=cls.create_unit_of_work)

    @classmethod
    def create_result_html_reader(cls) -> ScrapingResultHtmlReader:
        """Cria o leitor de HTML bruto para enriquecimento de links (P0d)."""
        return DefaultScrapingResultHtmlReader(
            get_scraping_result=cls.create_get_scraping_result(),
        )

    @classmethod
    def create_job_submitter(cls) -> ScrapingJobSubmitter:
        """Cria o contrato publico para submeter/acompanhar jobs (Orchestration V2)."""

        return DefaultScrapingJobSubmitter(
            create_scraping_job=cls.create_create_scraping_job(),
            get_scraping_job=cls.create_get_scraping_job(),
        )
