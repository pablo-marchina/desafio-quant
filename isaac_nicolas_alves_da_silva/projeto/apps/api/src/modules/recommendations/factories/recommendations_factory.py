"""Composicao das dependencias concretas do modulo recommendations."""

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.nvidia_knowledge.factories.nvidia_knowledge_factory import (
    NvidiaKnowledgeFactory,
)
from apps.api.src.modules.rag.factories.rag_factory import RagFactory
from apps.api.src.modules.recommendations.application.ports import (
    NvidiaKnowledgeGrounder,
    NvidiaSemanticCandidateSelector,
)
from apps.api.src.modules.recommendations.application.use_cases.generate_recommendations import (
    GenerateRecommendations,
)
from apps.api.src.modules.recommendations.application.use_cases.get_recommendation import (
    GetRecommendation,
)
from apps.api.src.modules.recommendations.application.use_cases.get_technology_stats import (
    GetTechnologyStats,
)
from apps.api.src.modules.recommendations.application.use_cases.list_recommendations import (
    ListRecommendations,
)
from apps.api.src.modules.recommendations.application.use_cases.review_recommendation import (
    ReviewRecommendation,
)
from apps.api.src.modules.recommendations.application.public.recommendation_generator import (
    RecommendationGenerator,
)
from apps.api.src.modules.recommendations.application.public.recommendation_justification_updater import (
    RecommendationJustificationUpdater,
)
from apps.api.src.modules.recommendations.application.public.recommendations_reader import (
    RecommendationsReader,
)
from apps.api.src.modules.recommendations.application.use_cases.update_recommendation_justifications import (
    UpdateRecommendationJustifications,
)
from apps.api.src.modules.recommendations.infrastructure.database.postgres_unit_of_work import (
    PostgresRecommendationsUnitOfWork,
)
from apps.api.src.modules.recommendations.infrastructure.nvidia_adapters.nvidia_catalog_adapter import (
    NvidiaKnowledgeCatalogAdapter,
)
from apps.api.src.modules.recommendations.infrastructure.rag_adapters.nvidia_knowledge_grounder_adapter import (
    RagNvidiaKnowledgeGrounder,
)
from apps.api.src.modules.recommendations.infrastructure.rag_adapters.semantic_candidate_selector_adapter import (
    RagSemanticNvidiaCandidateSelector,
)
from apps.api.src.modules.recommendations.infrastructure.startups_adapters.startup_profile_adapter import (
    StartupsModuleProfileSource,
)
from apps.api.src.modules.startups.factories.startups_factory import StartupsFactory


class RecommendationsFactory:
    """Ponto de composicao do modulo recommendations."""

    @staticmethod
    def create_nvidia_knowledge_grounder() -> NvidiaKnowledgeGrounder | None:
        """Sem `GEMINI_API_KEY`, devolve `None` - sem fundamentacao via RAG."""

        if not get_settings().gemini_api_key:
            return None
        return RagNvidiaKnowledgeGrounder(RagFactory.create_question_answerer())

    @staticmethod
    def create_semantic_candidate_selector() -> NvidiaSemanticCandidateSelector:
        """Pre-seletor de candidatos via retrieval semantico no nvidia_knowledge.

        Sempre disponivel — usa busca hibrida (Qdrant + BM25). Sem
        GEMINI_API_KEY, o retrieval semantico vetorial falha e o adapter
        devolve set() vazio (fallback para todos os candidatos).
        """
        return RagSemanticNvidiaCandidateSelector(RagFactory.create_search_evidence())

    @staticmethod
    def create_generate_recommendations() -> GenerateRecommendations:
        catalog_source = NvidiaKnowledgeCatalogAdapter(
            NvidiaKnowledgeFactory.create_catalog()
        )
        profile_source = StartupsModuleProfileSource(
            StartupsFactory.create_startup_profile_reader()
        )
        return GenerateRecommendations(
            PostgresRecommendationsUnitOfWork,
            profile_source,
            catalog_source,
            grounder=RecommendationsFactory.create_nvidia_knowledge_grounder(),
            semantic_selector=RecommendationsFactory.create_semantic_candidate_selector(),
        )

    @staticmethod
    def create_recommendation_justification_updater() -> RecommendationJustificationUpdater:
        return UpdateRecommendationJustifications(PostgresRecommendationsUnitOfWork)

    @staticmethod
    def create_get_recommendation() -> GetRecommendation:
        return GetRecommendation(PostgresRecommendationsUnitOfWork)

    @staticmethod
    def create_list_recommendations() -> ListRecommendations:
        return ListRecommendations(PostgresRecommendationsUnitOfWork)

    @staticmethod
    def create_recommendations_reader() -> RecommendationsReader:
        return ListRecommendations(PostgresRecommendationsUnitOfWork)

    @staticmethod
    def create_get_technology_stats() -> GetTechnologyStats:
        return GetTechnologyStats(PostgresRecommendationsUnitOfWork)

    @staticmethod
    def create_review_recommendation() -> ReviewRecommendation:
        return ReviewRecommendation(PostgresRecommendationsUnitOfWork)

    @staticmethod
    def create_recommendation_generator() -> RecommendationGenerator:
        catalog_source = NvidiaKnowledgeCatalogAdapter(
            NvidiaKnowledgeFactory.create_catalog()
        )
        profile_source = StartupsModuleProfileSource(
            StartupsFactory.create_startup_profile_reader()
        )
        return GenerateRecommendations(
            PostgresRecommendationsUnitOfWork,
            profile_source,
            catalog_source,
            grounder=RecommendationsFactory.create_nvidia_knowledge_grounder(),
            semantic_selector=RecommendationsFactory.create_semantic_candidate_selector(),
        )
