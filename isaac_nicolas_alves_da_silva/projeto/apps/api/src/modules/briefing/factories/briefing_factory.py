"""Composicao das dependencias concretas do modulo briefing."""

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.briefing.application.ports import NvidiaContextGrounder
from apps.api.src.modules.briefing.application.use_cases.generate_briefing import (
    GenerateBriefing,
)
from apps.api.src.modules.briefing.application.use_cases.get_briefing import (
    GetBriefing,
)
from apps.api.src.modules.briefing.application.use_cases.list_briefings import (
    ListBriefings,
)
from apps.api.src.modules.briefing.application.use_cases.review_briefing import (
    ReviewBriefing,
)
from apps.api.src.modules.briefing.application.public.briefing_content_updater import (
    BriefingContentUpdater,
)
from apps.api.src.modules.briefing.application.public.briefing_generator import (
    BriefingGenerator,
)
from apps.api.src.modules.briefing.application.use_cases.update_briefing_content import (
    UpdateBriefingContent,
)
from apps.api.src.modules.briefing.application.use_cases.export_briefing_pdf import (
    ExportBriefingPdf,
)
from apps.api.src.modules.briefing.infrastructure.database.postgres_unit_of_work import (
    PostgresBriefingsUnitOfWork,
)
from apps.api.src.modules.briefing.infrastructure.rag_adapters.nvidia_context_grounder_adapter import (
    RagNvidiaContextGrounder,
)
from apps.api.src.modules.briefing.infrastructure.rendering.jinja_playwright_pdf_renderer import (
    JinjaPlaywrightPdfRenderer,
)
from apps.api.src.modules.briefing.infrastructure.recommendations_adapters.recommendations_adapter import (
    RecommendationsModuleSource,
)
from apps.api.src.modules.briefing.infrastructure.startups_adapters.startup_profile_adapter import (
    StartupsModuleProfileSource,
)
from apps.api.src.modules.rag.factories.rag_factory import RagFactory
from apps.api.src.modules.recommendations.factories.recommendations_factory import (
    RecommendationsFactory,
)
from apps.api.src.modules.startups.factories.startups_factory import StartupsFactory


class BriefingFactory:
    """Ponto de composicao do modulo briefing."""

    @staticmethod
    def create_nvidia_context_grounder() -> NvidiaContextGrounder | None:
        """Sem `GEMINI_API_KEY`, devolve `None` - sem fundamentacao via RAG."""

        if not get_settings().gemini_api_key:
            return None
        return RagNvidiaContextGrounder(RagFactory.create_question_answerer())

    @staticmethod
    def create_generate_briefing() -> GenerateBriefing:
        profile_source = StartupsModuleProfileSource(
            StartupsFactory.create_startup_profile_reader()
        )
        recommendations_source = RecommendationsModuleSource(
            RecommendationsFactory.create_recommendations_reader()
        )
        return GenerateBriefing(
            PostgresBriefingsUnitOfWork,
            profile_source,
            recommendations_source,
            grounder=BriefingFactory.create_nvidia_context_grounder(),
        )

    @staticmethod
    def create_get_briefing() -> GetBriefing:
        return GetBriefing(PostgresBriefingsUnitOfWork)

    @staticmethod
    def create_list_briefings() -> ListBriefings:
        return ListBriefings(PostgresBriefingsUnitOfWork)

    @staticmethod
    def create_briefing_generator() -> BriefingGenerator:
        profile_source = StartupsModuleProfileSource(
            StartupsFactory.create_startup_profile_reader()
        )
        recommendations_source = RecommendationsModuleSource(
            RecommendationsFactory.create_recommendations_reader()
        )
        return GenerateBriefing(
            PostgresBriefingsUnitOfWork,
            profile_source,
            recommendations_source,
            grounder=BriefingFactory.create_nvidia_context_grounder(),
        )

    @staticmethod
    def create_briefing_content_updater() -> BriefingContentUpdater:
        return UpdateBriefingContent(PostgresBriefingsUnitOfWork)

    @staticmethod
    def create_export_briefing_pdf() -> ExportBriefingPdf:
        return ExportBriefingPdf(PostgresBriefingsUnitOfWork, JinjaPlaywrightPdfRenderer())

    @staticmethod
    def create_review_briefing() -> ReviewBriefing:
        return ReviewBriefing(PostgresBriefingsUnitOfWork)
