"""Caso de uso executado pelo ingestion_worker."""

from uuid import UUID

from apps.api.src.modules.ingestion.application.ports import ScrapingResultReader
from apps.api.src.modules.ingestion.application.text_cleaner import TextCleaner
from apps.api.src.modules.ingestion.application.text_chunker import TextChunker
from apps.api.src.modules.ingestion.application.unit_of_work import (
    IngestionUnitOfWorkFactory,
)
from apps.api.src.modules.ingestion.domain.entities import Chunk, Document, document_content_hash
from apps.api.src.modules.ingestion.domain.exceptions import (
    IngestionJobNotFoundError,
    IngestionSourceNotFoundError,
)


class ExecuteIngestionJob:
    """Transforma um scraping_result em documento limpo e chunks.

    Fluxo: start → ler scraping_result → limpar → chunkar → salvar
    documento + chunks → complete. Qualquer erro transitiona o job para
    FAILED e relanca para o Dramatiq (auditoria via erro_message).
    """

    def __init__(
        self,
        *,
        uow_factory: IngestionUnitOfWorkFactory,
        scraping_result_reader: ScrapingResultReader,
        text_cleaner: TextCleaner,
        text_chunker: TextChunker,
    ) -> None:
        self._uow_factory = uow_factory
        self._scraping_result_reader = scraping_result_reader
        self._text_cleaner = text_cleaner
        self._text_chunker = text_chunker

    async def execute(self, *, job_id: UUID) -> None:
        async with self._uow_factory() as uow:
            job = await uow.job_repository.get_by_id(job_id)
            if job is None:
                raise IngestionJobNotFoundError(
                    f"IngestionJob {job_id} nao encontrado."
                )

            job.start()

            try:
                result_data = await self._scraping_result_reader.get_by_id(
                    job.scraping_result_id
                )
                if result_data is None:
                    raise IngestionSourceNotFoundError(
                        f"scraping_result {job.scraping_result_id} nao encontrado."
                    )

                clean_text = self._text_cleaner.clean(result_data.raw_text)
                content_hash = document_content_hash(clean_text)

                # Dedup por conteudo: se o mesmo texto ja foi processado por outro
                # job (re-scrape pos-TTL com conteudo identico), reaproveita o
                # Document existente sem criar chunks nem chamar embedding de novo.
                existing_doc = await uow.document_repository.find_by_content_hash(
                    content_hash
                )
                if existing_doc is not None:
                    job.complete(existing_doc.id)
                else:
                    chunks_text = self._text_chunker.chunk(clean_text)

                    doc = Document(
                        ingestion_job_id=job.id,
                        scraping_result_id=job.scraping_result_id,
                        url=result_data.url,
                        title=result_data.title,
                        clean_text=clean_text,
                        word_count=len(clean_text.split()) if clean_text else 0,
                        chunk_count=len(chunks_text),
                        content_hash=content_hash,
                        source_type=job.source_type,
                    )

                    chunks = [
                        Chunk(
                            document_id=doc.id,
                            chunk_index=i,
                            text=text,
                            word_count=len(text.split()),
                            char_count=len(text),
                        )
                        for i, text in enumerate(chunks_text)
                    ]

                    await uow.document_repository.save(doc)
                    for chunk in chunks:
                        await uow.chunk_repository.save(chunk)

                    job.complete(doc.id)

            except Exception as exc:
                job.fail(f"{type(exc).__name__}: {exc}")

            await uow.job_repository.save(job)
            await uow.commit()
