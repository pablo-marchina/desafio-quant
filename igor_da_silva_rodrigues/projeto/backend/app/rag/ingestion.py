from __future__ import annotations

from collections.abc import Sequence
from functools import partial

import requests

from app.core.contracts import validate_contract
from app.core.observability import LOGGER, logged_stage
from app.core.retry import execute_with_retry
from app.core.schemas import IngestionReport, KnowledgeSourceInput
from app.rag.chunking import NVIDIAChunker
from app.rag.document_loader import NVIDIADocumentLoader
from app.rag.knowledge_sources import NVIDIA_KNOWLEDGE_SOURCES
from app.rag.vector_store import QdrantKnowledgeStore


class NVIDIAKnowledgeIngestor:
    def __init__(
        self,
        loader: NVIDIADocumentLoader | None = None,
        chunker: NVIDIAChunker | None = None,
        store: QdrantKnowledgeStore | None = None,
        retry_wait_multiplier: float = 2.0,
    ) -> None:
        self.loader = loader or NVIDIADocumentLoader()
        self.chunker = chunker or NVIDIAChunker(chunk_size=800, chunk_overlap=100)
        self.store = store or QdrantKnowledgeStore()
        self.retry_wait_multiplier = retry_wait_multiplier

    def run(
        self,
        sources: Sequence[KnowledgeSourceInput] | None = None,
        batch_size: int = 100,
    ) -> IngestionReport:
        selected_sources = list(sources or NVIDIA_KNOWLEDGE_SOURCES)
        all_chunks = []
        errors = []
        processed = 0

        with logged_stage("nvidia_knowledge_ingestion", source_count=len(selected_sources)) as metrics:
            for source in selected_sources:
                try:
                    document, _ = execute_with_retry(
                        partial(self.loader.load, source),
                        stage=f"load:{source.tecnologia}",
                        retryable=(requests.RequestException, ValueError),
                        wait_multiplier=self.retry_wait_multiplier,
                    )
                    chunks = self.chunker.split(document)
                    all_chunks.extend(chunks)
                    processed += 1
                    LOGGER.info(
                        "knowledge_source_processed",
                        tecnologia=source.tecnologia,
                        url=source.url,
                        chunks=len(chunks),
                    )
                except (requests.RequestException, ValueError) as exc:
                    errors.append(f"{source.url}: {exc}")
                    LOGGER.error("knowledge_source_failed", url=source.url, error=str(exc))

            inserted = self.store.upsert_chunks(all_chunks, batch_size=batch_size) if all_chunks else 0
            metrics["result_count"] = inserted

        status = "completo" if not errors else "parcial" if processed else "falha"
        report = {
            "status": status,
            "fontes_processadas": processed,
            "fontes_com_erro": len(errors),
            "chunks_gerados": len(all_chunks),
            "chunks_inseridos": inserted,
            "collection_name": self.store.config.collection_name,
            "errors": errors,
        }
        return validate_contract(IngestionReport, report)
