"""Caso de uso para submeter fontes NVIDIA Knowledge a coleta."""

from apps.api.src.modules.nvidia_knowledge.application.dto import (
    ListNvidiaKnowledgeSourcesInput,
    SubmittedNvidiaKnowledgeSourceView,
    SubmitNvidiaKnowledgeSourcesInput,
    SubmitNvidiaKnowledgeSourcesView,
)
from apps.api.src.modules.nvidia_knowledge.application.ports import (
    NvidiaKnowledgeUrlIngestionSubmitter,
)
from apps.api.src.modules.nvidia_knowledge.application.public.source_registry import (
    NvidiaKnowledgeSourceRegistry,
)


class SubmitNvidiaKnowledgeSources:
    """Submete fontes do registry para scraping, preservando o contexto NVIDIA."""

    def __init__(
        self,
        *,
        source_registry: NvidiaKnowledgeSourceRegistry,
        url_ingestion_submitter: NvidiaKnowledgeUrlIngestionSubmitter,
    ) -> None:
        self._source_registry = source_registry
        self._url_ingestion_submitter = url_ingestion_submitter

    async def execute(
        self,
        submit_input: SubmitNvidiaKnowledgeSourcesInput,
    ) -> SubmitNvidiaKnowledgeSourcesView:
        sources = await self._source_registry.list_sources(
            ListNvidiaKnowledgeSourcesInput(
                priority=submit_input.priority,
                technology_slug=submit_input.technology_slug,
                query=submit_input.query,
            )
        )

        if submit_input.limit is not None:
            sources = sources[: submit_input.limit]

        submitted: list[SubmittedNvidiaKnowledgeSourceView] = []
        for source in sources:
            url_ingestion_job_id = await self._url_ingestion_submitter.submit(
                source.url,
                source_type=source.document_source_type,
            )
            submitted.append(
                SubmittedNvidiaKnowledgeSourceView(
                    source_slug=source.slug,
                    title=source.title,
                    url=source.url,
                    priority=source.priority,
                    technology_slug=source.technology_slug,
                    url_ingestion_job_id=str(url_ingestion_job_id),
                )
            )

        return SubmitNvidiaKnowledgeSourcesView(
            total=len(submitted),
            submitted=submitted,
        )
