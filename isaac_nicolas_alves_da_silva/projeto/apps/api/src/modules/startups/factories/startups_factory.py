"""Composicao das dependencias concretas do modulo startups."""

from apps.api.src.modules.agents.factories.agents_factory import AgentsFactory
from apps.api.src.modules.startups.application.use_cases.add_startup_evidence import (
    AddStartupEvidence,
)
from apps.api.src.modules.startups.application.use_cases.classify_startup import (
    ClassifyStartup,
)
from apps.api.src.modules.startups.application.use_cases.create_startup import (
    CreateStartup,
)
from apps.api.src.modules.startups.application.use_cases.extract_startup_profile import (
    ExtractStartupProfile,
)
from apps.api.src.modules.startups.application.use_cases.get_startup import GetStartup
from apps.api.src.modules.startups.application.use_cases.get_startup_profile import (
    GetStartupProfile,
)
from apps.api.src.modules.startups.application.use_cases.list_startup_evidences import (
    ListStartupEvidences,
)
from apps.api.src.modules.startups.application.use_cases.get_portfolio_stats import (
    GetPortfolioStats,
)
from apps.api.src.modules.startups.application.use_cases.list_startups import (
    ListStartups,
)
from apps.api.src.modules.startups.application.use_cases.update_startup import (
    UpdateStartup,
)
from apps.api.src.modules.startups.infrastructure.agent_adapters.agents_extractor import (
    AgentsExtractor,
)
from apps.api.src.modules.startups.infrastructure.agent_adapters.agents_startup_classifier import (
    AgentsStartupClassifier,
)
from apps.api.src.modules.startups.infrastructure.database.postgres_unit_of_work import (
    PostgresStartupsUnitOfWork,
)


class StartupsFactory:
    """Ponto de composicao do modulo startups."""

    @staticmethod
    def create_create_startup() -> CreateStartup:
        return CreateStartup(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_get_startup() -> GetStartup:
        return GetStartup(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_list_startups() -> ListStartups:
        return ListStartups(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_get_portfolio_stats() -> GetPortfolioStats:
        return GetPortfolioStats(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_update_startup() -> UpdateStartup:
        return UpdateStartup(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_add_startup_evidence() -> AddStartupEvidence:
        return AddStartupEvidence(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_list_startup_evidences() -> ListStartupEvidences:
        return ListStartupEvidences(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_startup_profile_reader() -> GetStartupProfile:
        return GetStartupProfile(PostgresStartupsUnitOfWork)

    @staticmethod
    def create_classify_startup() -> ClassifyStartup:
        classification_service = AgentsFactory.create_startup_classification_service()
        classifier = (
            AgentsStartupClassifier(classification_service)
            if classification_service is not None
            else None
        )
        return ClassifyStartup(PostgresStartupsUnitOfWork, classifier)

    @staticmethod
    def create_extract_startup_profile() -> ExtractStartupProfile:
        extraction_service = AgentsFactory.create_extraction_service()
        extractor = (
            AgentsExtractor(extraction_service)
            if extraction_service is not None
            else None
        )
        return ExtractStartupProfile(PostgresStartupsUnitOfWork, extractor)
