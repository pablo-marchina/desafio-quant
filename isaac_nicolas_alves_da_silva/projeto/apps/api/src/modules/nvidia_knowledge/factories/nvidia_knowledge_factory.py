"""Composicao das dependencias concretas do modulo NVIDIA Knowledge."""

from apps.api.src.modules.nvidia_knowledge.application.use_cases.list_nvidia_technologies import (
    ListNvidiaTechnologies,
)
from apps.api.src.modules.nvidia_knowledge.application.use_cases.list_nvidia_knowledge_sources import (
    ListNvidiaKnowledgeSources,
)
from apps.api.src.modules.nvidia_knowledge.application.use_cases.submit_nvidia_knowledge_sources import (
    SubmitNvidiaKnowledgeSources,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.orchestration_adapters.url_ingestion_submitter_adapter import (
    UrlIngestionSubmitterAdapter,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.static_source_repository import (
    StaticNvidiaKnowledgeSourceRepository,
)
from apps.api.src.modules.nvidia_knowledge.infrastructure.static_catalog.static_repository import (
    StaticNvidiaTechnologyRepository,
)


class NvidiaKnowledgeFactory:
    """Ponto de composicao do modulo NVIDIA Knowledge."""

    @staticmethod
    def create_catalog() -> ListNvidiaTechnologies:
        return ListNvidiaTechnologies(StaticNvidiaTechnologyRepository())

    @staticmethod
    def create_source_registry() -> ListNvidiaKnowledgeSources:
        return ListNvidiaKnowledgeSources(StaticNvidiaKnowledgeSourceRepository())

    @staticmethod
    def create_submit_sources_for_ingestion() -> SubmitNvidiaKnowledgeSources:
        from apps.api.src.modules.orchestration.factories.orchestration_factory import (
            OrchestrationFactory,
        )

        source_registry = NvidiaKnowledgeFactory.create_source_registry()
        url_ingestion_submitter = UrlIngestionSubmitterAdapter(
            OrchestrationFactory.create_create_url_ingestion_job()
        )
        return SubmitNvidiaKnowledgeSources(
            source_registry=source_registry,
            url_ingestion_submitter=url_ingestion_submitter,
        )
